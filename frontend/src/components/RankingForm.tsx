'use client'

import { useState } from 'react'
import axios from 'axios'
import { TrendingUp, Plus, X, Loader2 } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001'

interface RankingFormProps {
  candidates: any[]
  onRankingComplete: (rankedCandidates: any[]) => void
}

export default function RankingForm({ candidates, onRankingComplete }: RankingFormProps) {
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    jobTitle: '',
    jobDescription: '',
    requiredSkills: [''],
    preferredSkills: [''],
    minYearsExperience: 0,
    requiredEducation: '',
  })

  const addSkillField = (type: 'required' | 'preferred') => {
    if (type === 'required') {
      setFormData({ ...formData, requiredSkills: [...formData.requiredSkills, ''] })
    } else {
      setFormData({ ...formData, preferredSkills: [...formData.preferredSkills, ''] })
    }
  }

  const removeSkillField = (type: 'required' | 'preferred', index: number) => {
    if (type === 'required') {
      const newSkills = formData.requiredSkills.filter((_, i) => i !== index)
      setFormData({ ...formData, requiredSkills: newSkills.length > 0 ? newSkills : [''] })
    } else {
      const newSkills = formData.preferredSkills.filter((_, i) => i !== index)
      setFormData({ ...formData, preferredSkills: newSkills })
    }
  }

  const updateSkill = (type: 'required' | 'preferred', index: number, value: string) => {
    if (type === 'required') {
      const newSkills = [...formData.requiredSkills]
      newSkills[index] = value
      setFormData({ ...formData, requiredSkills: newSkills })
    } else {
      const newSkills = [...formData.preferredSkills]
      newSkills[index] = value
      setFormData({ ...formData, preferredSkills: newSkills })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.jobTitle || !formData.jobDescription) {
      alert('Please fill in job title and description')
      return
    }

    const requiredSkills = formData.requiredSkills.filter(s => s.trim() !== '')
    if (requiredSkills.length === 0) {
      alert('Please add at least one required skill')
      return
    }

    setLoading(true)

    try {
      const response = await axios.post(`${API_URL}/api/candidates/rank`, {
        jobTitle: formData.jobTitle,
        jobDescription: formData.jobDescription,
        requiredSkills,
        preferredSkills: formData.preferredSkills.filter(s => s.trim() !== ''),
        minYearsExperience: formData.minYearsExperience,
        requiredEducation: formData.requiredEducation,
      })

      onRankingComplete(response.data)
    } catch (error: any) {
      alert(error.response?.data?.message || 'Failed to rank candidates')
    } finally {
      setLoading(false)
    }
  }

  if (candidates.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-12 text-center">
        <TrendingUp className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <p className="text-gray-600 mb-2">No candidates available to rank</p>
        <p className="text-sm text-gray-500">Please upload some CVs first</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Rank Candidates</h2>
      <p className="text-gray-600 mb-6">
        Define job requirements to rank {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Job Title */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Job Title *
          </label>
          <input
            type="text"
            value={formData.jobTitle}
            onChange={(e) => setFormData({ ...formData, jobTitle: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="e.g., Senior Full Stack Developer"
            disabled={loading}
          />
        </div>

        {/* Job Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Job Description *
          </label>
          <textarea
            value={formData.jobDescription}
            onChange={(e) => setFormData({ ...formData, jobDescription: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            rows={4}
            placeholder="Describe the role, responsibilities, and what you're looking for..."
            disabled={loading}
          />
        </div>

        {/* Required Skills */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Required Skills *
          </label>
          <div className="space-y-2">
            {formData.requiredSkills.map((skill, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  value={skill}
                  onChange={(e) => updateSkill('required', index, e.target.value)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="e.g., React, Node.js, TypeScript"
                  disabled={loading}
                />
                {formData.requiredSkills.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeSkillField('required', index)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-md"
                    disabled={loading}
                  >
                    <X size={20} />
                  </button>
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => addSkillField('required')}
            className="mt-2 flex items-center gap-2 text-primary-600 hover:text-primary-700 text-sm"
            disabled={loading}
          >
            <Plus size={16} />
            Add skill
          </button>
        </div>

        {/* Preferred Skills */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Preferred Skills (Optional)
          </label>
          <div className="space-y-2">
            {formData.preferredSkills.map((skill, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  value={skill}
                  onChange={(e) => updateSkill('preferred', index, e.target.value)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="e.g., GraphQL, Docker"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => removeSkillField('preferred', index)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-md"
                  disabled={loading}
                >
                  <X size={20} />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => addSkillField('preferred')}
            className="mt-2 flex items-center gap-2 text-primary-600 hover:text-primary-700 text-sm"
            disabled={loading}
          >
            <Plus size={16} />
            Add skill
          </button>
        </div>

        {/* Additional Criteria */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Minimum Years of Experience
            </label>
            <input
              type="number"
              min="0"
              value={formData.minYearsExperience}
              onChange={(e) => setFormData({ ...formData, minYearsExperience: parseInt(e.target.value) || 0 })}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              disabled={loading}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Required Education
            </label>
            <input
              type="text"
              value={formData.requiredEducation}
              onChange={(e) => setFormData({ ...formData, requiredEducation: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="e.g., Bachelor's in Computer Science"
              disabled={loading}
            />
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-primary-500 text-white rounded-md hover:bg-primary-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin" size={20} />
              Ranking candidates...
            </>
          ) : (
            <>
              <TrendingUp size={20} />
              Rank Candidates
            </>
          )}
        </button>
      </form>
    </div>
  )
}
