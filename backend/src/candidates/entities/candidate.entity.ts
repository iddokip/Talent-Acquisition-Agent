import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export interface Education {
  degree: string;
  institution: string;
  startDate: string;
  endDate: string;
  fieldOfStudy?: string;
}

export interface Experience {
  title: string;
  company: string;
  startDate: string;
  endDate: string;
  description: string;
  responsibilities?: string[];
}

export interface ParsedData {
  rawText: string;
  sections: {
    personalInfo?: any;
    skills?: any;
    experience?: any;
    education?: any;
  };
}

export interface ScoringDetails {
  skillsScore: number;
  experienceScore: number;
  educationScore: number;
  overallScore: number;
  reasoning: string;
}

@Entity('candidates')
export class Candidate {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  email: string;

  @Column()
  fullName: string;

  @Column({ nullable: true })
  phone: string;

  @Column('simple-array', { nullable: true })
  skills: string[];

  @Column('jsonb', { nullable: true })
  experience: Experience[];

  @Column('jsonb', { nullable: true })
  education: Education[];

  @Column({ nullable: true })
  cvFilePath: string;

  @Column('jsonb', { nullable: true })
  parsedData: ParsedData;

  @Column('float', { nullable: true, default: 0 })
  score: number;

  @Column('jsonb', { nullable: true })
  scoringDetails: ScoringDetails;

  @Column({ nullable: true })
  yearsOfExperience: number;

  @Column({ default: 'pending' })
  status: string; // pending, reviewed, shortlisted, rejected

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
}
