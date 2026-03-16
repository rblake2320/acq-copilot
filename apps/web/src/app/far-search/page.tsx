'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Search, BookOpen, ExternalLink, ChevronDown, ChevronUp,
  Loader2, AlertCircle, ChevronRight, RefreshCw, Zap, FileText
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

// ─── Types ────────────────────────────────────────────────────────────────────

interface FARResult {
  section: string
  title: string
  content: string
  regulation: string
  part: number
  source_url: string
  score: number
}

interface SearchResponse {
  results: FARResult[]
  query: string
  total_found: number
  search_method: string
}

interface RAGStatus {
  status: string
  total_sections: number
  sections_with_embeddings: number
  sections_by_regulation: Record<string, number>
}

interface PartSection {
  section: string
  title: string
  content: string
  source_url: string
}

// ─── FAR Part metadata ────────────────────────────────────────────────────────

const FAR_PARTS: Record<number, string> = {
  1: 'Federal Acquisition Regulations System',
  2: 'Definitions of Words and Terms',
  3: 'Improper Business Practices',
  4: 'Administrative and Information Matters',
  5: 'Publicizing Contract Actions',
  6: 'Competition Requirements',
  7: 'Acquisition Planning',
  8: 'Required Sources of Supplies and Services',
  9: 'Contractor Qualifications',
  10: 'Market Research',
  11: 'Describing Agency Needs',
  12: 'Commercial Products and Commercial Services',
  13: 'Simplified Acquisition Procedures',
  14: 'Sealed Bidding',
  15: 'Contracting by Negotiation',
  16: 'Types of Contracts',
  17: 'Special Contracting Methods',
  18: 'Emergency Acquisitions',
  19: 'Small Business Programs',
  22: 'Application of Labor Laws',
  23: 'Environment, Energy, and Water Efficiency',
  24: 'Protection of Privacy',
  25: 'Foreign Acquisition',
  26: 'Other Socioeconomic Programs',
  27: 'Patents, Data, and Copyrights',
  28: 'Bonds and Insurance',
  29: 'Taxes',
  30: 'Cost Accounting Standards',
  31: 'Contract Cost Principles and Procedures',
  32: 'Contract Financing',
  33: 'Protests, Disputes, and Appeals',
  34: 'Major System Acquisition',
  35: 'Research and Development Contracting',
  36: 'Construction and Architect-Engineer Contracts',
  37: 'Service Contracting',
  38: 'Federal Supply Schedule Contracting',
  39: 'Acquisition of Information Technology',
  41: 'Acquisition of Utility Services',
  42: 'Contract Administration and Audit Services',
  43: 'Contract Modifications',
  44: 'Subcontracting Policies and Procedures',
  45: 'Government Property',
  46: 'Quality Assurance',
  47: 'Transportation',
  48: 'Value Engineering',
  49: 'Termination of Contracts',
  50: 'Extraordinary Contractual Actions',
  51: 'Use of Government Sources by Contractors',
  52: 'Solicitation Provisions and Contract Clauses',
  53: 'Forms',
}

// FAC 2026-01 — effective 03/13/2026 (current)
const FAC_CHANGES = [
  { section: '22.1503(b)(2)', change: '$102,280 → $105,767', case: 'FAR Case 2025-007', type: 'threshold' },
  { section: '25.202(c)', change: '$6,708,000 → $6,683,000', case: 'FAR Case 2025-007', type: 'threshold' },
  { section: '25.402', change: 'Table revision', case: 'FAR Case 2025-007', type: 'table' },
  { section: '25.603(c)(1)', change: '$6,708,000 → $6,683,000', case: 'FAR Case 2025-007', type: 'threshold' },
  { section: '25.1101(b)(1)(iii) & (b)(2)(iii)', change: '$102,280 → $105,767', case: 'FAR Case 2025-007', type: 'threshold' },
]

const EXAMPLE_SEARCHES = [
  'simplified acquisition threshold',
  'small business set-aside requirements',
  'commercial item definition',
  'source selection criteria best value',
  'contract termination for convenience',
  'cure notice requirements',
  'past performance evaluation',
  'indefinite delivery indefinite quantity',
]

// ─── Component ────────────────────────────────────────────────────────────────

export default function FARSearchPage() {
  const [query, setQuery] = useState('')
  const [regulation, setRegulation] = useState<string>('')
  const [part, setPart] = useState<string>('')
  const [results, setResults] = useState<FARResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchMeta, setSearchMeta] = useState<{ total: number; method: string } | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  // Part browser
  const [selectedPart, setSelectedPart] = useState<number | null>(null)
  const [partSections, setPartSections] = useState<PartSection[]>([])
  const [partLoading, setPartLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'search' | 'browse' | 'changes'>('search')

  // Corpus status
  const [ragStatus, setRagStatus] = useState<RAGStatus | null>(null)

  useEffect(() => {
    fetch('/api/rag/status').then(r => r.json()).then(setRagStatus).catch(() => {})
  }, [])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setIsLoading(true)
    setError(null)
    setActiveTab('search')

    try {
      const res = await fetch('/api/rag/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          regulation: regulation || null,
          part: part ? parseInt(part) : null,
          top_k: 8,
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Search failed')
      }
      const data: SearchResponse = await res.json()
      setResults(data.results)
      setSearchMeta({ total: data.total_found, method: data.search_method })
      setExpanded({})
    } catch (err: any) {
      setError(err.message || 'Failed to search FAR')
    } finally {
      setIsLoading(false)
    }
  }

  const loadPart = useCallback(async (partNum: number) => {
    setSelectedPart(partNum)
    setPartLoading(true)
    setActiveTab('browse')
    try {
      const res = await fetch(`/api/rag/far/${partNum}`)
      if (!res.ok) throw new Error('Part not found')
      const data = await res.json()
      setPartSections(data.sections || [])
    } catch {
      setPartSections([])
    } finally {
      setPartLoading(false)
    }
  }, [])

  const toggleExpand = (key: string) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))

  const getScoreBadge = (score: number) => {
    if (score >= 0.8) return <Badge className="bg-emerald-900 text-emerald-300 text-xs">High Match</Badge>
    if (score >= 0.6) return <Badge className="bg-blue-900 text-blue-300 text-xs">Good Match</Badge>
    return <Badge className="bg-slate-700 text-slate-300 text-xs">Partial</Badge>
  }

  const corpusEmpty = ragStatus?.total_sections === 0
  const corpusReady = ragStatus && ragStatus.total_sections > 0

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── Left: Part Navigator ──────────────────────────────────────────── */}
      <aside className="w-52 flex-shrink-0 border-r border-slate-700 bg-slate-900 flex flex-col overflow-hidden">
        <div className="px-3 py-3 border-b border-slate-700">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">FAR Parts</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          <div className="p-2 space-y-0.5">
            {/* All 53 parts */}
            {Array.from({ length: 53 }, (_, i) => i + 1).map(num => {
              const title = FAR_PARTS[num]
              if (!title) return null // reserved parts (20, 21, 40)
              const isSelected = selectedPart === num
              return (
                <button
                  key={num}
                  onClick={() => loadPart(num)}
                  className={`w-full text-left px-2 py-1.5 rounded text-xs flex items-center gap-2 transition-colors ${
                    isSelected
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                  }`}
                >
                  <span className={`font-mono font-bold flex-shrink-0 w-5 ${isSelected ? 'text-blue-200' : 'text-slate-500'}`}>
                    {num}
                  </span>
                  <span className="truncate leading-tight">{title}</span>
                </button>
              )
            })}
          </div>

          {/* DFARS / Changes */}
          <div className="p-2 border-t border-slate-700 mt-1 space-y-0.5">
            <button
              onClick={() => setActiveTab('changes')}
              className={`w-full text-left px-2 py-1.5 rounded text-xs flex items-center gap-2 transition-colors ${
                activeTab === 'changes'
                  ? 'bg-amber-700 text-white'
                  : 'text-amber-400 hover:bg-slate-800'
              }`}
            >
              <Zap className="w-3 h-3 flex-shrink-0" />
              <span>FAC 2026-01 Changes</span>
            </button>
          </div>
        </div>

        {/* Corpus status */}
        <div className="p-3 border-t border-slate-700">
          {ragStatus ? (
            <div className="text-xs space-y-0.5">
              <div className={`font-medium ${corpusReady ? 'text-emerald-400' : 'text-amber-400'}`}>
                {corpusReady ? `${ragStatus.total_sections.toLocaleString()} sections` : 'Corpus building…'}
              </div>
              {corpusReady && (
                <div className="text-slate-500">{ragStatus.sections_with_embeddings.toLocaleString()} embedded</div>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-600">Loading…</div>
          )}
        </div>
      </aside>

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Search bar — always visible */}
        <div className="flex-shrink-0 border-b border-slate-700 bg-slate-900 px-6 py-4">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Ask anything about FAR/DFARS — e.g. 'sole source justification thresholds'"
                className="pl-9 bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
              />
            </div>
            <select
              value={regulation}
              onChange={e => setRegulation(e.target.value)}
              className="bg-slate-800 border border-slate-600 text-slate-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">All Regs</option>
              <option value="FAR">FAR</option>
              <option value="DFARS">DFARS</option>
            </select>
            <Button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="bg-blue-600 hover:bg-blue-700 px-6"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
            </Button>
          </form>

          {/* Tabs */}
          <div className="flex gap-1 mt-3">
            {(['search', 'browse', 'changes'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 text-xs font-medium rounded-full transition-colors capitalize ${
                  activeTab === tab
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab === 'search' ? '🧠 Semantic Search' : tab === 'browse' ? '📖 Browse by Part' : '⚡ Recent Changes'}
              </button>
            ))}
          </div>
        </div>

        {/* Corpus empty warning */}
        {corpusEmpty && (
          <div className="m-4 p-4 bg-amber-950/50 border border-amber-800 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-300 text-sm font-medium">FAR corpus is being built</p>
              <p className="text-amber-500 text-xs mt-1">
                53 FAR parts are being ingested and embedded right now. Search will work once complete (~5–10 min).
                Keyword fallback is active in the meantime.
              </p>
            </div>
          </div>
        )}

        {/* ── SEARCH TAB ──────────────────────────────────────────────────── */}
        {activeTab === 'search' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-4">

            {/* Example chips */}
            {results.length === 0 && !isLoading && !error && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  {corpusReady
                    ? `Searching ${ragStatus?.total_sections.toLocaleString()} FAR/DFARS sections with AI semantic similarity`
                    : 'Semantic search powered by nomic-embed-text — finds relevant sections even without exact keyword matches'}
                </p>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_SEARCHES.map(ex => (
                    <button
                      key={ex}
                      onClick={() => { setQuery(ex); }}
                      className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-600 transition-colors"
                    >
                      {ex}
                    </button>
                  ))}
                </div>

                {/* What makes this different */}
                <div className="mt-6 grid grid-cols-3 gap-4">
                  {[
                    { icon: '🧠', title: 'Semantic, not keyword', desc: 'Finds "sole source justification" when you ask about "buying without competition"' },
                    { icon: '⚡', title: 'FAC 2026-01 current', desc: 'Corpus reflects the March 13, 2026 update — acquisition.gov is keyword-only on the same data' },
                    { icon: '🔗', title: 'Direct section links', desc: 'Every result links to the authoritative acquisition.gov text for citation' },
                  ].map(f => (
                    <div key={f.title} className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                      <div className="text-2xl mb-2">{f.icon}</div>
                      <p className="text-slate-200 text-sm font-medium">{f.title}</p>
                      <p className="text-slate-500 text-xs mt-1">{f.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <Card className="bg-red-950 border-red-800">
                <CardContent className="pt-4">
                  <p className="text-red-300 text-sm">{error}</p>
                </CardContent>
              </Card>
            )}

            {/* Results meta */}
            {searchMeta && !isLoading && (
              <div className="flex items-center gap-3 text-sm text-slate-400">
                <span className="font-medium text-slate-200">{searchMeta.total} results</span>
                <Badge variant="outline" className="text-slate-400 border-slate-600">
                  {searchMeta.method === 'semantic' ? '🧠 Semantic' : '🔍 Keyword'} search
                </Badge>
              </div>
            )}

            {/* Search results */}
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <Card key={i} className="bg-slate-800 border-slate-700 animate-pulse">
                    <CardHeader>
                      <div className="h-4 bg-slate-700 rounded w-1/4 mb-2" />
                      <div className="h-5 bg-slate-700 rounded w-3/4" />
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="h-3 bg-slate-700 rounded" />
                        <div className="h-3 bg-slate-700 rounded w-5/6" />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {results.map((result, idx) => {
                  const key = `${result.section}-${idx}`
                  const isExpanded = expanded[key]
                  return (
                    <Card key={key} className="bg-slate-800 border-slate-700">
                      <CardHeader className="pb-2">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <Badge className="bg-slate-700 text-slate-300 font-mono text-xs">
                                {result.regulation} {result.section}
                              </Badge>
                              <Badge variant="outline" className="text-slate-400 border-slate-600 text-xs">
                                Part {result.part}
                              </Badge>
                              {getScoreBadge(result.score)}
                            </div>
                            <CardTitle className="text-slate-100 text-base leading-snug">
                              {result.title}
                            </CardTitle>
                          </div>
                          <a
                            href={result.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300 flex-shrink-0 mt-1"
                            title="Open on acquisition.gov"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <p className="text-slate-300 text-sm leading-relaxed">
                          {isExpanded ? result.content : result.content.slice(0, 350) + (result.content.length > 350 ? '…' : '')}
                        </p>
                        {result.content.length > 350 && (
                          <button
                            onClick={() => toggleExpand(key)}
                            className="mt-2 flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                          >
                            {isExpanded ? <><ChevronUp className="w-3 h-3" /> Show less</> : <><ChevronDown className="w-3 h-3" /> Show full text</>}
                          </button>
                        )}
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* ── BROWSE TAB ──────────────────────────────────────────────────── */}
        {activeTab === 'browse' && (
          <div className="flex-1 overflow-y-auto p-6">
            {!selectedPart ? (
              <div className="space-y-3">
                <p className="text-slate-400 text-sm">Select a FAR Part from the left panel to browse its sections.</p>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(FAR_PARTS).slice(0, 12).map(([num, title]) => (
                    <button
                      key={num}
                      onClick={() => loadPart(parseInt(num))}
                      className="text-left p-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors group"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-slate-500 w-6">P{num}</span>
                        <span className="text-slate-300 text-sm group-hover:text-white truncate">{title}</span>
                        <ChevronRight className="w-3 h-3 text-slate-600 ml-auto flex-shrink-0" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : partLoading ? (
              <div className="flex items-center gap-3 text-slate-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Loading FAR Part {selectedPart}…</span>
              </div>
            ) : partSections.length === 0 ? (
              <div className="space-y-3">
                <div className="p-4 bg-slate-800 border border-slate-700 rounded-lg">
                  <p className="text-slate-300 text-sm font-medium">FAR Part {selectedPart}: {FAR_PARTS[selectedPart]}</p>
                  <p className="text-slate-500 text-xs mt-2">
                    This part hasn't been ingested yet. The corpus build is in progress.
                  </p>
                  <a
                    href={`https://www.acquisition.gov/far/part-${selectedPart}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-blue-400 text-xs mt-3 hover:text-blue-300"
                  >
                    View on acquisition.gov <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-slate-100 font-semibold">
                      FAR Part {selectedPart}: {FAR_PARTS[selectedPart]}
                    </h2>
                    <p className="text-slate-500 text-xs mt-0.5">{partSections.length} sections</p>
                  </div>
                  <a
                    href={`https://www.acquisition.gov/far/part-${selectedPart}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                  >
                    acquisition.gov <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                {partSections.map((sec, idx) => {
                  const key = `part-${idx}`
                  const isExpanded = expanded[key]
                  return (
                    <div key={idx} className="border border-slate-700 rounded-lg bg-slate-800">
                      <button
                        onClick={() => toggleExpand(key)}
                        className="w-full text-left px-4 py-3 flex items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="font-mono text-xs text-slate-400 flex-shrink-0">{sec.section}</span>
                          <span className="text-slate-200 text-sm truncate">{sec.title}</span>
                        </div>
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-500 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-500 flex-shrink-0" />}
                      </button>
                      {isExpanded && (
                        <div className="px-4 pb-4 border-t border-slate-700">
                          <p className="text-slate-300 text-sm leading-relaxed mt-3">{sec.content}</p>
                          <a
                            href={sec.source_url || `https://www.acquisition.gov/far/part-${selectedPart}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 mt-3"
                          >
                            Authoritative source <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* ── CHANGES TAB ─────────────────────────────────────────────────── */}
        {activeTab === 'changes' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <div>
              <h2 className="text-slate-100 font-semibold flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-400" />
                FAC 2026-01 — Effective March 13, 2026
              </h2>
              <p className="text-slate-400 text-sm mt-1">
                Federal Acquisition Circular 2026-01 updates economic thresholds and trade act values.
              </p>
            </div>

            <div className="border border-slate-700 rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 border-b border-slate-700">
                  <tr>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Section</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Change</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Case</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {FAC_CHANGES.map((change, idx) => (
                    <tr key={idx} className="bg-slate-900 hover:bg-slate-800 transition-colors">
                      <td className="px-4 py-3 font-mono text-blue-400 text-xs">{change.section}</td>
                      <td className="px-4 py-3 text-slate-300">{change.change}</td>
                      <td className="px-4 py-3 text-slate-500 text-xs">{change.case}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => {
                            setQuery(`FAR ${change.section}`)
                            setActiveTab('search')
                          }}
                          className="text-xs text-blue-400 hover:text-blue-300"
                        >
                          Search →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Card className="bg-slate-800 border-slate-700">
              <CardContent className="pt-4">
                <p className="text-slate-300 text-sm font-medium mb-1">What changed in FAC 2026-01</p>
                <ul className="text-slate-400 text-xs space-y-1.5">
                  <li>• <strong className="text-slate-300">Service Contract Act (SCA) wage threshold</strong> — raised from $102,280 to $105,767 in FAR 22.1503 and 25.1101</li>
                  <li>• <strong className="text-slate-300">Trade Agreements Act (TAA) threshold</strong> — adjusted from $6,708,000 to $6,683,000 in FAR 25.202, 25.402, and 25.603</li>
                  <li>• All changes reflect WTO GPA and bilateral FTA adjustments effective 03/13/2026</li>
                </ul>
                <a
                  href="https://www.acquisition.gov/far/current/html/AFARS_APPENDIX-AA.html"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 mt-3"
                >
                  Full FAC 2026-01 on acquisition.gov <ExternalLink className="w-3 h-3" />
                </a>
              </CardContent>
            </Card>

            {/* Key thresholds quick reference */}
            <div>
              <h3 className="text-slate-300 font-medium text-sm mb-3">Key Acquisition Thresholds (current)</h3>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Micro-Purchase Threshold', value: '$10,000', part: 'FAR 2.101' },
                  { label: 'Simplified Acquisition Threshold', value: '$250,000', part: 'FAR 2.101' },
                  { label: 'Commercial Products SAT', value: '$7.5M', part: 'FAR 12.102' },
                  { label: 'TINA Threshold', value: '$2M', part: 'FAR 15.403-4' },
                  { label: 'SB Set-Aside (mandatory)', value: '≤$250K', part: 'FAR 19.502-2' },
                  { label: 'SCA Coverage Threshold', value: '$2,500', part: 'FAR 22.1003-3' },
                  { label: 'TAA Threshold (current)', value: '$6,683,000', part: 'FAR 25.402' },
                  { label: 'SCA Wage Index (updated)', value: '$105,767', part: 'FAR 22.1503' },
                ].map(t => (
                  <div key={t.label} className="bg-slate-800 border border-slate-700 rounded-lg p-3">
                    <p className="text-slate-400 text-xs">{t.label}</p>
                    <p className="text-slate-100 font-semibold text-lg mt-0.5">{t.value}</p>
                    <button
                      onClick={() => { setQuery(t.label); setActiveTab('search') }}
                      className="text-xs text-slate-500 hover:text-blue-400 mt-1 font-mono"
                    >
                      {t.part}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
