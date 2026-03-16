'use client'

import { useState, useCallback } from 'react'
import {
  Shield, Upload, FileText, AlertCircle, CheckCircle2,
  XCircle, Info, ExternalLink, Loader2, ChevronDown, ChevronUp
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface ComplianceIssue {
  severity: 'error' | 'warning' | 'info'
  category: string
  clause_number?: string
  description: string
  recommendation: string
  far_reference?: string
}

interface ExtractedClause {
  clause_number: string
  clause_title?: string
  regulation: string
  found_at_page?: number
}

interface ComplianceReport {
  score: number
  grade: string
  clauses_found: string[]
  issues: ComplianceIssue[]
  required_missing: string[]
  recommended_missing: string[]
  contract_type_detected?: string
  set_aside_detected?: string
  value_threshold_detected?: string
  summary: string
}

interface CheckResult {
  filename: string
  parse: {
    clauses_extracted: number
    page_count: number
    word_count: number
    parse_method: string
    clauses: ExtractedClause[]
  }
  compliance: ComplianceReport
}

const GRADE_COLORS: Record<string, string> = {
  A: 'text-emerald-400',
  B: 'text-blue-400',
  C: 'text-yellow-400',
  D: 'text-orange-400',
  F: 'text-red-400',
}

const SEVERITY_CONFIG = {
  error: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-950/50 border-red-800', label: 'Required' },
  warning: { icon: AlertCircle, color: 'text-amber-400', bg: 'bg-amber-950/50 border-amber-800', label: 'Recommended' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-950/50 border-blue-800', label: 'Info' },
}

export default function CompliancePage() {
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<CheckResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pastedText, setPastedText] = useState('')
  const [showPasteMode, setShowPasteMode] = useState(false)
  const [showClauses, setShowClauses] = useState(false)

  const uploadFile = useCallback(async (file: File) => {
    setIsLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/compliance/check', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Compliance check failed')
      }

      const data: CheckResult = await res.json()
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Failed to check compliance')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const checkPastedText = async () => {
    if (!pastedText.trim()) return
    setIsLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await fetch('/api/compliance/check-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: pastedText, filename: 'pasted-solicitation' }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Compliance check failed')
      }

      const data = await res.json()
      setResult({ filename: 'Pasted Text', parse: { ...data.parse, page_count: 1, word_count: pastedText.split(' ').length, parse_method: 'text' }, compliance: data.compliance })
    } catch (err: any) {
      setError(err.message || 'Failed to check compliance')
    } finally {
      setIsLoading(false)
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
  }

  const scoreColor = result
    ? result.compliance.score >= 90 ? 'text-emerald-400'
    : result.compliance.score >= 70 ? 'text-blue-400'
    : result.compliance.score >= 50 ? 'text-amber-400'
    : 'text-red-400'
    : ''

  return (
    <div className="flex flex-col h-full p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Shield className="w-6 h-6 text-purple-400" />
          Solicitation Compliance Checker
        </h1>
        <p className="text-slate-400 mt-1">
          Upload a solicitation PDF or paste text to check FAR/DFARS clause compliance
        </p>
      </div>

      {/* Upload area */}
      {!result && !isLoading && (
        <div className="space-y-4">
          {/* Drop zone */}
          <div
            onDrop={onDrop}
            onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            className={`
              relative border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer
              ${isDragging ? 'border-purple-500 bg-purple-500/10' : 'border-slate-600 hover:border-slate-500'}
            `}
          >
            <input
              type="file"
              accept=".pdf,.docx,.doc,.txt,.rtf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.gif,.webp"
              onChange={onFileInput}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <Upload className="w-10 h-10 text-slate-500 mx-auto mb-3" />
            <p className="text-slate-300 font-medium">Drop solicitation file here or click to browse</p>
            <p className="text-slate-500 text-sm mt-1">PDF, DOCX, TXT, RTF, or images (PNG, JPG, TIFF) — max 10MB</p>
          </div>

          <div className="text-center text-slate-500 text-sm">— or —</div>

          {/* Paste mode */}
          {!showPasteMode ? (
            <Button
              variant="outline"
              onClick={() => setShowPasteMode(true)}
              className="w-full border-slate-600 text-slate-300 hover:bg-slate-800"
            >
              <FileText className="w-4 h-4 mr-2" />
              Paste solicitation text
            </Button>
          ) : (
            <div className="space-y-2">
              <textarea
                value={pastedText}
                onChange={e => setPastedText(e.target.value)}
                placeholder="Paste solicitation text here (clause list, sections, full text)..."
                className="w-full h-48 bg-slate-800 border border-slate-600 text-slate-200 rounded-lg p-3 text-sm resize-none placeholder:text-slate-500 focus:outline-none focus:border-purple-500"
              />
              <div className="flex gap-2">
                <Button
                  onClick={checkPastedText}
                  disabled={!pastedText.trim()}
                  className="bg-purple-700 hover:bg-purple-600"
                >
                  Check Compliance
                </Button>
                <Button
                  variant="outline"
                  onClick={() => { setShowPasteMode(false); setPastedText('') }}
                  className="border-slate-600 text-slate-400"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <Loader2 className="w-12 h-12 text-purple-400 animate-spin" />
          <p className="text-slate-400">Parsing document and checking FAR compliance...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <Card className="bg-red-950 border-red-800">
          <CardContent className="pt-4 flex items-start gap-3">
            <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-300 text-sm">{error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setError(null); setResult(null) }}
                className="mt-2 border-red-800 text-red-400"
              >
                Try again
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Score card */}
          <Card className="bg-slate-800 border-slate-700">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-400 text-sm">Compliance Score</p>
                  <div className="flex items-baseline gap-3 mt-1">
                    <span className={`text-5xl font-bold ${scoreColor}`}>
                      {result.compliance.score}
                    </span>
                    <span className="text-slate-500 text-xl">/100</span>
                    <span className={`text-3xl font-bold ${GRADE_COLORS[result.compliance.grade] || 'text-slate-400'}`}>
                      Grade {result.compliance.grade}
                    </span>
                  </div>
                  <p className="text-slate-400 text-sm mt-2">{result.compliance.summary}</p>
                </div>
                <div className="text-right space-y-1">
                  {result.compliance.contract_type_detected && (
                    <Badge className="bg-slate-700 text-slate-300 block">
                      {result.compliance.contract_type_detected}
                    </Badge>
                  )}
                  {result.compliance.set_aside_detected && (
                    <Badge className="bg-emerald-900 text-emerald-300 block">
                      {result.compliance.set_aside_detected}
                    </Badge>
                  )}
                  {result.compliance.value_threshold_detected && (
                    <Badge className="bg-blue-900 text-blue-300 block">
                      {result.compliance.value_threshold_detected}
                    </Badge>
                  )}
                </div>
              </div>

              {/* Parse stats */}
              <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-slate-700">
                <div className="text-center">
                  <p className="text-2xl font-bold text-slate-200">{result.parse.clauses_extracted}</p>
                  <p className="text-slate-500 text-xs">Clauses Found</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-400">{result.compliance.required_missing.length}</p>
                  <p className="text-slate-500 text-xs">Required Missing</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-400">{result.compliance.recommended_missing.length}</p>
                  <p className="text-slate-500 text-xs">Recommended Missing</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Issues list */}
          {result.compliance.issues.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-slate-300 font-semibold text-sm uppercase tracking-wide">
                Findings ({result.compliance.issues.length})
              </h2>
              {result.compliance.issues.map((issue, idx) => {
                const cfg = SEVERITY_CONFIG[issue.severity]
                const Icon = cfg.icon
                return (
                  <Card key={idx} className={`${cfg.bg} border`}>
                    <CardContent className="pt-4">
                      <div className="flex items-start gap-3">
                        <Icon className={`w-5 h-5 ${cfg.color} flex-shrink-0 mt-0.5`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge className="bg-slate-700 text-slate-300 text-xs">
                              {cfg.label}
                            </Badge>
                            {issue.clause_number && (
                              <span className="font-mono text-xs text-slate-400">{issue.clause_number}</span>
                            )}
                            <span className="text-xs text-slate-500 capitalize">{issue.category.replace(/_/g, ' ')}</span>
                          </div>
                          <p className="text-slate-200 text-sm">{issue.description}</p>
                          <p className="text-slate-400 text-xs mt-1">
                            Recommendation: {issue.recommendation}
                          </p>
                          {issue.far_reference && (
                            <a
                              href={`https://www.acquisition.gov/far/part-${issue.far_reference.replace(/[^0-9.]/g, '').split('.')[0]}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 mt-1"
                            >
                              {issue.far_reference} <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}

          {/* Clauses found (collapsible) */}
          {result.parse.clauses.length > 0 && (
            <div>
              <button
                onClick={() => setShowClauses(!showClauses)}
                className="flex items-center gap-2 text-slate-400 hover:text-slate-300 text-sm"
              >
                {showClauses ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                Clauses found in document ({result.parse.clauses.length})
              </button>
              {showClauses && (
                <div className="mt-2 grid grid-cols-1 gap-1">
                  {result.parse.clauses.map((clause, idx) => (
                    <div key={idx} className="flex items-center gap-3 py-1 text-sm border-b border-slate-700/50">
                      <span className="font-mono text-xs text-slate-400 w-24 flex-shrink-0">{clause.clause_number}</span>
                      <Badge variant="outline" className="text-xs border-slate-700 text-slate-500">{clause.regulation}</Badge>
                      <span className="text-slate-300">{clause.clause_title || 'Unknown clause'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Check another */}
          <Button
            variant="outline"
            onClick={() => { setResult(null); setError(null) }}
            className="border-slate-600 text-slate-300"
          >
            Check another document
          </Button>
        </div>
      )}
    </div>
  )
}
