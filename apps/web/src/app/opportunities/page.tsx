'use client'

import { useState } from 'react'
import { Search, Building2, Calendar, DollarSign, ExternalLink, MapPin, Tag, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface Opportunity {
  notice_id: string
  title: string
  solicitation_number?: string
  posted_date?: string
  response_deadline?: string
  agency: string
  office?: string
  naics_code?: string
  set_aside?: string
  place_of_performance?: string
  contract_type?: string
  estimated_value?: string
  description?: string
  active: boolean
  sam_url: string
}

interface SearchResult {
  data: {
    opportunities: Opportunity[]
    total_records: number
    query: string
  }
  api_key_configured: boolean
  sam_url: string
}

const SET_ASIDE_OPTIONS = [
  { code: '', label: 'All Set-Asides' },
  { code: 'SBA', label: 'Small Business' },
  { code: '8A', label: '8(a)' },
  { code: 'HZC', label: 'HUBZone' },
  { code: 'SDVOSBC', label: 'SDVOSB' },
  { code: 'WOSB', label: 'WOSB' },
]

const US_STATES = [
  '', 'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
  'VA','WA','WV','WI','WY','DC',
]

export default function OpportunitiesPage() {
  const [query, setQuery] = useState('')
  const [naics, setNaics] = useState('')
  const [state, setState] = useState('')
  const [setAside, setSetAside] = useState('')
  const [results, setResults] = useState<Opportunity[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [meta, setMeta] = useState<{ total: number; sam_url: string; api_configured: boolean } | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/opportunities/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim() || '',
          naics_code: naics || null,
          state: state || null,
          set_aside: setAside || null,
          limit: 12,
        }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Search failed')
      }

      const data: SearchResult = await res.json()
      setResults(data.data?.opportunities || [])
      setMeta({
        total: data.data?.total_records || 0,
        sam_url: data.sam_url,
        api_configured: data.api_key_configured,
      })
    } catch (err: any) {
      setError(err.message || 'Failed to search opportunities')
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return null
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    } catch {
      return dateStr
    }
  }

  const isUrgent = (deadline?: string) => {
    if (!deadline) return false
    const days = (new Date(deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
    return days <= 7 && days >= 0
  }

  return (
    <div className="flex flex-col h-full p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Building2 className="w-6 h-6 text-emerald-400" />
          Contract Opportunities
        </h1>
        <p className="text-slate-400 mt-1">
          Search active federal contract opportunities from SAM.gov
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
              placeholder="e.g. IT services, cybersecurity, cloud infrastructure..."
              className="pl-9 bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>
          <Button type="submit" disabled={isLoading} className="bg-emerald-700 hover:bg-emerald-600">
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search SAM.gov'}
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          <Input
            value={naics}
            onChange={e => setNaics(e.target.value)}
            placeholder="NAICS code"
            className="w-32 bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            maxLength={6}
          />
          <select
            value={state}
            onChange={e => setState(e.target.value)}
            className="bg-slate-800 border border-slate-600 text-slate-300 rounded-md px-3 py-2 text-sm"
          >
            <option value="">All States</option>
            {US_STATES.filter(Boolean).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            value={setAside}
            onChange={e => setSetAside(e.target.value)}
            className="bg-slate-800 border border-slate-600 text-slate-300 rounded-md px-3 py-2 text-sm"
          >
            {SET_ASIDE_OPTIONS.map(o => (
              <option key={o.code} value={o.code}>{o.label}</option>
            ))}
          </select>
        </div>
      </form>

      {/* API key warning */}
      {meta && !meta.api_configured && (
        <Card className="bg-amber-950/50 border-amber-800">
          <CardContent className="pt-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-300 text-sm font-medium">SAM.gov API key not configured</p>
              <p className="text-amber-500 text-xs mt-1">
                Get a free key at <a href="https://api.data.gov/signup" target="_blank" rel="noopener noreferrer" className="underline">api.data.gov</a> and add <code className="font-mono">SAM_API_KEY=your_key</code> to your .env file.
                {' '}<a href={meta.sam_url} target="_blank" rel="noopener noreferrer" className="underline">Search SAM.gov directly →</a>
              </p>
            </div>
          </CardContent>
        </Card>
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
      {meta && (
        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>{meta.total.toLocaleString()} total opportunities found</span>
          <a href={meta.sam_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-blue-400 hover:text-blue-300">
            View on SAM.gov <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && results.length === 0 && !error && !meta && (
        <div className="space-y-3">
          <p className="text-sm text-slate-500">Quick searches:</p>
          <div className="flex flex-wrap gap-2">
            {['IT services', 'cybersecurity', 'cloud storage', 'software development', 'training services', 'logistics'].map(ex => (
              <button key={ex} onClick={() => setQuery(ex)} className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-600">
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Opportunity cards */}
      <div className="grid grid-cols-1 gap-4">
        {results.map(opp => (
          <Card key={opp.notice_id} className="bg-slate-800 border-slate-700 hover:border-slate-500 transition-colors">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    {opp.set_aside && (
                      <Badge className="bg-emerald-900 text-emerald-300 text-xs">{opp.set_aside}</Badge>
                    )}
                    {opp.contract_type && (
                      <Badge variant="outline" className="text-slate-400 border-slate-600 text-xs">{opp.contract_type}</Badge>
                    )}
                    {opp.naics_code && (
                      <Badge variant="outline" className="text-slate-500 border-slate-700 text-xs font-mono">NAICS {opp.naics_code}</Badge>
                    )}
                    {isUrgent(opp.response_deadline) && (
                      <Badge className="bg-red-900 text-red-300 text-xs animate-pulse">⚡ Deadline Soon</Badge>
                    )}
                  </div>
                  <CardTitle className="text-slate-100 text-sm font-semibold leading-snug">
                    {opp.title}
                  </CardTitle>
                </div>
                <a href={opp.sam_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 flex-shrink-0">
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {opp.description && (
                <p className="text-slate-400 text-xs leading-relaxed line-clamp-2">{opp.description}</p>
              )}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-400">
                <div className="flex items-center gap-1.5">
                  <Building2 className="w-3 h-3 text-slate-500 flex-shrink-0" />
                  <span className="truncate">{opp.agency}</span>
                </div>
                {opp.place_of_performance && (
                  <div className="flex items-center gap-1.5">
                    <MapPin className="w-3 h-3 text-slate-500 flex-shrink-0" />
                    <span>{opp.place_of_performance}</span>
                  </div>
                )}
                {opp.posted_date && (
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-3 h-3 text-slate-500 flex-shrink-0" />
                    <span>Posted {formatDate(opp.posted_date)}</span>
                  </div>
                )}
                {opp.response_deadline && (
                  <div className={`flex items-center gap-1.5 ${isUrgent(opp.response_deadline) ? 'text-red-400' : ''}`}>
                    <Calendar className="w-3 h-3 flex-shrink-0" />
                    <span>Due {formatDate(opp.response_deadline)}</span>
                  </div>
                )}
                {opp.solicitation_number && (
                  <div className="flex items-center gap-1.5 col-span-2">
                    <Tag className="w-3 h-3 text-slate-500 flex-shrink-0" />
                    <span className="font-mono">{opp.solicitation_number}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <Card key={i} className="bg-slate-800 border-slate-700 animate-pulse">
              <CardHeader>
                <div className="flex gap-2 mb-2">
                  <div className="h-5 bg-slate-700 rounded-full w-20" />
                  <div className="h-5 bg-slate-700 rounded-full w-16" />
                </div>
                <div className="h-4 bg-slate-700 rounded w-3/4" />
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-2">
                  <div className="h-3 bg-slate-700 rounded" />
                  <div className="h-3 bg-slate-700 rounded" />
                  <div className="h-3 bg-slate-700 rounded" />
                  <div className="h-3 bg-slate-700 rounded" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
