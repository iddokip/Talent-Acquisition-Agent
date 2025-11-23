'use client'

import { useState } from 'react'
import axios from 'axios'
import { Upload, Users, TrendingUp } from 'lucide-react'
import CVUpload from '@/components/CVUpload'
import CandidateList from '@/components/CandidateList'
import RankingForm from '@/components/RankingForm'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001'

export default function Home() {
  const [activeTab, setActiveTab] = useState<'upload' | 'candidates' | 'rank'>('upload')
  const [candidates, setCandidates] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const fetchCandidates = async () => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_URL}/api/candidates`)
      setCandidates(response.data)
    } catch (error) {
      console.error('Error fetching candidates:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCVUploaded = () => {
    fetchCandidates()
    setActiveTab('candidates')
  }

  const handleRankingComplete = (rankedCandidates: any[]) => {
    setCandidates(rankedCandidates)
    setActiveTab('candidates')
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            🤖 AI Recruitment System
          </h1>
          <p className="text-gray-600">
            Automated CV Parsing & Intelligent Candidate Ranking
          </p>
        </div>

        {/* Navigation Tabs */}
        <div className="flex justify-center mb-8">
          <div className="bg-white rounded-lg shadow-md p-1 inline-flex">
            <button
              onClick={() => setActiveTab('upload')}
              className={`flex items-center gap-2 px-6 py-3 rounded-md transition-all ${
                activeTab === 'upload'
                  ? 'bg-primary-500 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <Upload size={20} />
              Upload CV
            </button>
            <button
              onClick={() => {
                setActiveTab('candidates')
                fetchCandidates()
              }}
              className={`flex items-center gap-2 px-6 py-3 rounded-md transition-all ${
                activeTab === 'candidates'
                  ? 'bg-primary-500 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <Users size={20} />
              Candidates
            </button>
            <button
              onClick={() => {
                setActiveTab('rank')
                fetchCandidates()
              }}
              className={`flex items-center gap-2 px-6 py-3 rounded-md transition-all ${
                activeTab === 'rank'
                  ? 'bg-primary-500 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <TrendingUp size={20} />
              Rank Candidates
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="max-w-6xl mx-auto">
          {activeTab === 'upload' && (
            <CVUpload onUploadSuccess={handleCVUploaded} />
          )}
          
          {activeTab === 'candidates' && (
            <CandidateList candidates={candidates} loading={loading} onRefresh={fetchCandidates} />
          )}
          
          {activeTab === 'rank' && (
            <RankingForm candidates={candidates} onRankingComplete={handleRankingComplete} />
          )}
        </div>

        {/* Footer */}
        <div className="text-center mt-16 text-gray-500 text-sm">
          <p>Ahmed Eltaher</p>
        </div>
      </div>
    </main>
  )
}
