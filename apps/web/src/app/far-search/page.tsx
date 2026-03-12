'use client'

import { useState } from 'react'
import { Search, BookOpen, ExternalLink, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

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

export default function FARSearchPage() {
  const [query, setQuery] = useState('')
  const [regulation, setRegulation] = useState<string>('')
  const [part, setPart] = useState<string>('')
  const [results, setResults] = useState<FARResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchMeta, setSearchMeta] = useState<{ total: number; method: string } | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setIsLoading(true)
    setError(null)

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

  const toggleExpand = (key: string) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const getScoreBadge = (score: number) => {
    if (score >= 0.8) return <Badge className="bg-emerald-900 text-emerald-300">High Match</Badge>
    if (score >= 0.6) return <Badge className="bg-blue-900 text-blue-300">Good Match</Badge>
    return <Badge className="bg-slate-700 text-slate-300">Partial Match</Badge>
  }

  return (
    <div className="flex flex-col h-full p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <BookOpen className="w-6 h-6 text-blue-400" />
          FAR / DFARS Semantic Search
        </h1>
        <p className="text-slate-400 mt-1">
          Search the full Federal Acquisition Regulation using AI-powered semantic similarity — not just keywords.
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch} className="space-y-3">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g. commercial item acquisition under $250K, small business set-aside requirements..."
              className="pl-9 bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>
          <Button type="submit" disabled={isLoading || !query.trim()} className="bg-blue-600 hover:bg-blue-700">
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
          </Button>
        </div>

        {/* Filters */}
        <div className="flex gap-3">
          <select
            value={regulation}
            onChange={e => setRegulation(e.target.value)}
            className="bg-slate-800 border border-slate-600 text-slate-300 rounded-md px-3 py-2 text-sm"
          >
            <option value="">All Regulations</option>
            <option value="FAR">FAR Only</option>
            <option value="DFARS">DFARS Only</option>
          </select>
          <Input
            type="number"
            value={part}
            onChange={e => setPart(e.target.value)}
            placeholder="Part # (optional)"
            className="w-36 bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            min={1}
            max={53}
          />
        </div>
      </form>

      {/* Example queries */}
      {results.length === 0 && !isLoading && !error && (
        <div className="space-y-2">
          <p className="text-sm text-slate-500">Example searches:</p>
          <div className="flex flex-wrap gap-2">
            {[
              'simplified acquisition threshold',
              'small business set-aside requirements',
              'commercial item definition',
              'source selection criteria',
              'contract termination for convenience',
              'cure notice requirements',
            ].map(example => (
              <button
                key={example}
                onClick={() => setQuery(example)}
                className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-600 transition-colors"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <Card className="bg-red-950 border-red-800">
          <CardContent className="pt-4">
            <p className="text-red-300 text-sm">{error}</p>
            <p className="text-red-500 text-xs mt-1">
              The FAR corpus may not be ingested yet. Run: <code className="font-mono">python -m app.services.far_ingest</code>
            </p>
          </CardContent>
        </Card>
      )}

      {/* Results meta */}
      {searchMeta && !isLoading && (
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span>{searchMeta.total} results</span>
          <Badge variant="outline" className="text-slate-400 border-slate-600">
            {searchMeta.method === 'semantic' ? '🧠 Semantic' : '🔍 Keyword'} search
          </Badge>
        </div>
      )}

      {/* Results */}
      <div className="space-y-3">
        {results.map((result, idx) => {
          const key = `${result.section}-${idx}`
          const isExpanded = expanded[key]

          return (
            <Card key={key} className="bg-slate-800 border-slate-700">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
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
                  {isExpanded ? result.content : result.content.slice(0, 300) + (result.content.length > 300 ? '…' : '')}
                </p>
                {result.content.length > 300 && (
                  <button
                    onClick={() => toggleExpand(key)}
                    className="mt-2 flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                  >
                    {isExpanded ? (
                      <><ChevronUp className="w-3 h-3" /> Show less</>
                    ) : (
                      <><ChevronDown className="w-3 h-3" /> Show more</>
                    )}
                  </button>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
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
                  <div className="h-3 bg-slate-700 rounded w-4/6" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
