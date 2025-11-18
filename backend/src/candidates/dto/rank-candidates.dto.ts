import { IsNotEmpty, IsString, IsArray, IsOptional } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class RankCandidatesDto {
  @ApiProperty({ description: 'Job title' })
  @IsString()
  @IsNotEmpty()
  jobTitle: string;

  @ApiProperty({ description: 'Job description' })
  @IsString()
  @IsNotEmpty()
  jobDescription: string;

  @ApiProperty({ description: 'Required skills', type: [String] })
  @IsArray()
  @IsNotEmpty()
  requiredSkills: string[];

  @ApiProperty({ description: 'Preferred skills', type: [String], required: false })
  @IsArray()
  @IsOptional()
  preferredSkills?: string[];

  @ApiProperty({ description: 'Minimum years of experience', required: false })
  @IsOptional()
  minYearsExperience?: number;

  @ApiProperty({ description: 'Required education level', required: false })
  @IsString()
  @IsOptional()
  requiredEducation?: string;
}
