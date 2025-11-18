import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { Candidate } from './entities/candidate.entity';
import { UploadCvDto } from './dto/upload-cv.dto';
import { RankCandidatesDto } from './dto/rank-candidates.dto';

@Injectable()
export class CandidatesService {
  private aiServiceUrl: string;

  constructor(
    @InjectRepository(Candidate)
    private candidatesRepository: Repository<Candidate>,
    private configService: ConfigService,
  ) {
    this.aiServiceUrl = this.configService.get<string>('AI_SERVICE_URL') || 'http://localhost:8001';
  }

  async uploadCv(uploadCvDto: UploadCvDto, file: Express.Multer.File): Promise<Candidate> {
    // Check if candidate already exists
    const existingCandidate = await this.candidatesRepository.findOne({
      where: { email: uploadCvDto.email },
    });

    if (existingCandidate) {
      throw new BadRequestException('Candidate with this email already exists');
    }

    // Save file
    const uploadDir = this.configService.get<string>('UPLOAD_DIR') || './uploads';
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }

    const fileName = `${Date.now()}-${file.originalname}`;
    const filePath = path.join(uploadDir, fileName);
    fs.writeFileSync(filePath, file.buffer);

    // Parse CV using AI service
    const parsedData = await this.parseCvWithAI(filePath);

    // Create candidate
    const candidate = this.candidatesRepository.create({
      email: uploadCvDto.email,
      fullName: uploadCvDto.fullName,
      phone: uploadCvDto.phone || parsedData.phone,
      skills: parsedData.skills || [],
      experience: parsedData.experience || [],
      education: parsedData.education || [],
      cvFilePath: filePath,
      parsedData: parsedData,
      yearsOfExperience: this.calculateYearsOfExperience(parsedData.experience),
      status: 'pending',
    });

    return await this.candidatesRepository.save(candidate);
  }

  async parseCvWithAI(filePath: string): Promise<any> {
    try {
      const formData = new FormData();
      const fileBuffer = fs.readFileSync(filePath);
      const blob = new Blob([fileBuffer]);
      formData.append('file', blob, path.basename(filePath));

      const response = await axios.post(
        `${this.aiServiceUrl}/parse-cv`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 30000, // 30 seconds
        },
      );

      return response.data;
    } catch (error) {
      console.error('Error parsing CV with AI service:', error.message);
      // Return basic structure if AI service fails
      return {
        skills: [],
        experience: [],
        education: [],
        phone: null,
      };
    }
  }

  async findAll(): Promise<Candidate[]> {
    return await this.candidatesRepository.find({
      order: { score: 'DESC', createdAt: 'DESC' },
    });
  }

  async findOne(id: string): Promise<Candidate> {
    const candidate = await this.candidatesRepository.findOne({ where: { id } });
    if (!candidate) {
      throw new NotFoundException(`Candidate with ID ${id} not found`);
    }
    return candidate;
  }

  async rankCandidates(rankDto: RankCandidatesDto): Promise<Candidate[]> {
    // Get all candidates
    const candidates = await this.candidatesRepository.find();

    if (candidates.length === 0) {
      return [];
    }

    try {
      // Call AI service to rank candidates
      const response = await axios.post(
        `${this.aiServiceUrl}/rank-candidates`,
        {
          job_requirements: {
            title: rankDto.jobTitle,
            description: rankDto.jobDescription,
            required_skills: rankDto.requiredSkills,
            preferred_skills: rankDto.preferredSkills || [],
            min_years_experience: rankDto.minYearsExperience || 0,
            required_education: rankDto.requiredEducation || '',
          },
          candidates: candidates.map((c) => ({
            id: c.id,
            email: c.email,
            full_name: c.fullName,
            skills: c.skills || [],
            experience: c.experience || [],
            education: c.education || [],
            years_of_experience: c.yearsOfExperience || 0,
          })),
        },
        { timeout: 60000 }, // 60 seconds for ranking
      );

      // Update candidates with scores
      const rankedCandidates = response.data.ranked_candidates;
      for (const rankedCandidate of rankedCandidates) {
        await this.candidatesRepository.update(
          { id: rankedCandidate.candidate_id },
          {
            score: rankedCandidate.score,
            scoringDetails: rankedCandidate.scoring_details,
          }
        );
      }

      // Fetch updated candidates
      return await this.candidatesRepository.find({
        order: { score: 'DESC' },
      });
    } catch (error) {
      console.error('Error ranking candidates:', error.message);
      throw new BadRequestException('Failed to rank candidates. AI service may be unavailable.');
    }
  }

  async deleteCandidate(id: string): Promise<void> {
    const candidate = await this.findOne(id);
    
    // Delete CV file if exists
    if (candidate.cvFilePath && fs.existsSync(candidate.cvFilePath)) {
      try {
        fs.unlinkSync(candidate.cvFilePath);
      } catch (error) {
        console.warn('Could not delete CV file:', error.message);
      }
    }

    // Call AI service to clean up cache and vector database (if endpoint exists)
    try {
      await axios.delete(`${this.aiServiceUrl}/cleanup-candidate/${id}`, {
        timeout: 5000,
      });
    } catch (error) {
      // This is optional - AI service may not have this endpoint yet
      console.log('AI service cleanup skipped (endpoint may not exist)');
    }

    // Delete from database
    const result = await this.candidatesRepository.delete(id);
    
    if (result.affected === 0) {
      throw new NotFoundException(`Candidate with ID ${id} not found`);
    }
  }

  private calculateYearsOfExperience(experience: any[]): number {
    if (!experience || experience.length === 0) {
      return 0;
    }

    let totalMonths = 0;
    for (const exp of experience) {
      const start = new Date(exp.startDate);
      const end = exp.endDate.toLowerCase() === 'present' ? new Date() : new Date(exp.endDate);
      const months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
      totalMonths += months;
    }

    return Math.round(totalMonths / 12 * 10) / 10; // Round to 1 decimal
  }
}
