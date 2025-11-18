import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  Delete,
  UseInterceptors,
  UploadedFile,
  BadRequestException,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ApiTags, ApiOperation, ApiConsumes, ApiBody } from '@nestjs/swagger';
import { CandidatesService } from './candidates.service';
import { UploadCvDto } from './dto/upload-cv.dto';
import { RankCandidatesDto } from './dto/rank-candidates.dto';

@ApiTags('candidates')
@Controller('candidates')
export class CandidatesController {
  constructor(private readonly candidatesService: CandidatesService) {}

  @Post('upload')
  @ApiOperation({ summary: 'Upload and parse a CV' })
  @ApiConsumes('multipart/form-data')
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        file: {
          type: 'string',
          format: 'binary',
        },
        email: {
          type: 'string',
        },
        fullName: {
          type: 'string',
        },
        phone: {
          type: 'string',
        },
      },
    },
  })
  @UseInterceptors(FileInterceptor('file'))
  async uploadCv(
    @Body() uploadCvDto: UploadCvDto,
    @UploadedFile() file: Express.Multer.File,
  ) {
    if (!file) {
      throw new BadRequestException('File is required');
    }

    // Validate file type
    const allowedMimeTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    if (!allowedMimeTypes.includes(file.mimetype)) {
      throw new BadRequestException('Only PDF and DOCX files are allowed');
    }

    return await this.candidatesService.uploadCv(uploadCvDto, file);
  }

  @Get()
  @ApiOperation({ summary: 'Get all candidates' })
  async findAll() {
    return await this.candidatesService.findAll();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get a candidate by ID' })
  async findOne(@Param('id') id: string) {
    return await this.candidatesService.findOne(id);
  }

  @Post('rank')
  @ApiOperation({ summary: 'Rank candidates based on job requirements' })
  async rankCandidates(@Body() rankDto: RankCandidatesDto) {
    return await this.candidatesService.rankCandidates(rankDto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Delete a candidate' })
  async deleteCandidate(@Param('id') id: string) {
    await this.candidatesService.deleteCandidate(id);
    return { message: 'Candidate deleted successfully' };
  }
}
