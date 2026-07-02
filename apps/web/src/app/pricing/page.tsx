'use client'

import { useState, useEffect, useCallback, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { DollarSign, TrendingUp, TrendingDown, Minus, Loader2, BarChart3, Save, FolderOpen, Trash2, X, Download, Share2, Check, Archive } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface PriceDataPoint {
  source: string
  label: string
  low?: number
  median?: number
  high?: number
  unit: string
  confidence: string
  notes?: string
}

interface PriceAnalysis {
  occupation: string
  location?: string
  experience_level?: string
  data_points: PriceDataPoint[]
  recommended_range_low?: number
  recommended_range_high?: number
  proposed_price?: number
  assessment?: string
  confidence: string
  summary: string
}

interface SavedAnalysis {
  id: string
  name: string
  savedAt: string
  archived: boolean
  form: { occupation: string; socCode: string; location: string; proposedRate: string; experience: string }
  result: PriceAnalysis
}

const STORAGE_KEY = 'acq_price_analyses'

function loadSaved(): SavedAnalysis[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') }
  catch { return [] }
}

function writeSaved(list: SavedAnalysis[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
}

function encodeShare(form: SavedAnalysis['form'], result: PriceAnalysis): string {
  const payload = JSON.stringify({ form, result })
  return btoa(encodeURIComponent(payload))
}

function decodeShare(encoded: string): { form: SavedAnalysis['form']; result: PriceAnalysis } | null {
  try { return JSON.parse(decodeURIComponent(atob(encoded))) }
  catch { return null }
}

function exportJson(entry: SavedAnalysis) {
  const blob = new Blob([JSON.stringify(entry, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `price-analysis-${entry.name.replace(/\s+/g, '-').toLowerCase()}-${new Date(entry.savedAt).toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function PricingInner() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const [occupation, setOccupation] = useState('')
  const [socCode, setSocCode] = useState('')
  const [location, setLocation] = useState('')
  const [proposedRate, setProposedRate] = useState('')
  const [experience, setExperience] = useState('mid')
  const [result, setResult] = useState<PriceAnalysis | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [saved, setSaved] = useState<SavedAnalysis[]>([])
  const [showSaved, setShowSaved] = useState(false)
  const [showArchived, setShowArchived] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sharedFrom, setSharedFrom] = useState(false)

  // Load from URL share param on mount
  useEffect(() => {
    const encoded = searchParams.get('s')
    if (encoded) {
      const decoded = decodeShare(encoded)
      if (decoded) {
        setOccupation(decoded.form.occupation)
        setSocCode(decoded.form.socCode)
        setLocation(decoded.form.location)
        setProposedRate(decoded.form.proposedRate)
        setExperience(decoded.form.experience)
        setResult(decoded.result)
        setSharedFrom(true)
        // Clean URL without navigating away
        router.replace('/pricing', { scroll: false })
      }
    }
  }, [])

  useEffect(() => { setSaved(loadSaved()) }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!occupation.trim()) return
    setIsLoading(true)
    setError(null)
    setSharedFrom(false)

    try {
      const res = await fetch('/api/pricing/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          occupation: occupation.trim(),
          soc_code: socCode || null,
          location: location || null,
          proposed_rate: proposedRate ? parseFloat(proposedRate) : null,
          experience_level: experience,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Analysis failed')
      const data = await res.json()
      setResult(data.analysis)
      setSaveName(occupation.trim())
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const currentForm = useCallback(() => ({
    occupation, socCode, location, proposedRate, experience
  }), [occupation, socCode, location, proposedRate, experience])

  const handleSave = (archive = false) => {
    if (!result) return
    const entry: SavedAnalysis = {
      id: Date.now().toString(),
      name: saveName || occupation || 'Analysis',
      savedAt: new Date().toISOString(),
      archived: archive,
      form: currentForm(),
      result,
    }
    const updated = [entry, ...saved]
    writeSaved(updated)
    setSaved(updated)
    setShowSaveDialog(false)
  }

  const toggleArchive = (id: string) => {
    const updated = saved.map(s => s.id === id ? { ...s, archived: !s.archived } : s)
    writeSaved(updated)
    setSaved(updated)
  }

  const handleLoad = (entry: SavedAnalysis) => {
    setOccupation(entry.form.occupation)
    setSocCode(entry.form.socCode)
    setLocation(entry.form.location)
    setProposedRate(entry.form.proposedRate)
    setExperience(entry.form.experience)
    setResult(entry.result)
    setError(null)
    setShowSaved(false)
  }

  const handleDelete = (id: string) => {
    const updated = saved.filter(s => s.id !== id)
    writeSaved(updated)
    setSaved(updated)
  }

  const handleShare = () => {
    if (!result) return
    const encoded = encodeShare(currentForm(), result)
    const url = `${window.location.origin}/pricing?s=${encoded}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  const handleExportCurrent = () => {
    if (!result) return
    const entry: SavedAnalysis = {
      id: Date.now().toString(),
      name: saveName || occupation,
      savedAt: new Date().toISOString(),
      archived: false,
      form: currentForm(),
      result,
    }
    exportJson(entry)
  }

  const fmt = (n?: number) => n != null ? `$${n.toFixed(2)}` : 'N/A'

  const getAssessmentConfig = (assessment?: string) => {
    switch (assessment) {
      case 'fair':  return { icon: Minus,     color: 'text-emerald-400', bg: 'bg-emerald-950/50 border-emerald-800', label: 'Fair Price' }
      case 'high':  return { icon: TrendingUp, color: 'text-red-400',     bg: 'bg-red-950/50 border-red-800',         label: 'Above Market' }
      case 'low':   return { icon: TrendingDown,color: 'text-amber-400',  bg: 'bg-amber-950/50 border-amber-800',     label: 'Below Market' }
      default:      return { icon: BarChart3,  color: 'text-slate-400',   bg: 'bg-slate-800 border-slate-700',        label: 'Insufficient Data' }
    }
  }

  const active   = saved.filter(s => !s.archived)
  const archived = saved.filter(s => s.archived)

  const renderList = (list: SavedAnalysis[], emptyMsg: string) => (
    list.length === 0
      ? <p className="text-slate-500 text-sm">{emptyMsg}</p>
      : <div className="space-y-2">
          {list.map(entry => {
            const cfg = getAssessmentConfig(entry.result.assessment)
            return (
              <div key={entry.id} className="flex items-center gap-2 p-2.5 rounded bg-slate-900/60 border border-slate-700 hover:border-slate-500 transition-colors">
                <button onClick={() => handleLoad(entry)} className="flex-1 text-left min-w-0">
                  <p className="text-slate-200 text-sm font-medium truncate">{entry.name}</p>
                  <p className="text-slate-500 text-xs truncate">
                    {entry.form.location || 'National'} · {entry.form.experience}
                    {entry.form.proposedRate ? ` · $${entry.form.proposedRate}/hr` : ''} · <span className={cfg.color}>{cfg.label}</span>
                  </p>
                  <p className="text-slate-600 text-xs">{new Date(entry.savedAt).toLocaleString()}</p>
                </button>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button onClick={() => exportJson(entry)} title="Export JSON" className="text-slate-600 hover:text-slate-300 p-1">
                    <Download className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => toggleArchive(entry.id)} title={entry.archived ? 'Unarchive' : 'Archive'} className="text-slate-600 hover:text-amber-400 p-1">
                    <Archive className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => handleDelete(entry.id)} title="Delete" className="text-slate-600 hover:text-red-400 p-1">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
  )

  return (
    <div className="flex flex-col h-full p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <DollarSign className="w-6 h-6 text-green-400" />
            Price Reasonableness Analyzer
          </h1>
          <p className="text-slate-400 mt-1">Cross-source price analysis: BLS OEWS 2024 + contractor billing rate model</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => { setShowSaved(!showSaved); setShowArchived(false) }}
          className="border-slate-600 text-slate-300 hover:bg-slate-700 flex items-center gap-1.5 flex-shrink-0"
        >
          <FolderOpen className="w-4 h-4" />
          Saved ({active.length})
          {archived.length > 0 && <span className="text-slate-500 ml-0.5">· {archived.length} archived</span>}
        </Button>
      </div>

      {sharedFrom && (
        <div className="flex items-center gap-2 px-3 py-2 rounded bg-blue-950/50 border border-blue-800 text-blue-300 text-sm">
          <Share2 className="w-4 h-4 flex-shrink-0" />
          Loaded from shared link — run Analyze Price to refresh data, or Save to keep it.
        </div>
      )}

      {/* Saved / Archive panel */}
      {showSaved && (
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowArchived(false)}
                  className={`text-sm font-medium pb-0.5 border-b-2 transition-colors ${!showArchived ? 'border-green-500 text-slate-200' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                >
                  Saved ({active.length})
                </button>
                <button
                  onClick={() => setShowArchived(true)}
                  className={`text-sm font-medium pb-0.5 border-b-2 transition-colors ${showArchived ? 'border-amber-500 text-slate-200' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                >
                  Archived ({archived.length})
                </button>
              </div>
              <button onClick={() => setShowSaved(false)} className="text-slate-500 hover:text-slate-300">
                <X className="w-4 h-4" />
              </button>
            </div>
          </CardHeader>
          <CardContent>
            {showArchived
              ? renderList(archived, 'No archived analyses.')
              : renderList(active, 'No saved analyses yet. Run an analysis and click Save.')}
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">Occupation / Labor Category</label>
            <Input value={occupation} onChange={e => setOccupation(e.target.value)}
              placeholder="e.g. Software Developer, Project Manager"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500" />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">BLS SOC Code (optional)</label>
            <Input value={socCode} onChange={e => setSocCode(e.target.value)}
              placeholder="15-1252"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500" />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">Location (optional)</label>
            <Input value={location} onChange={e => setLocation(e.target.value)}
              placeholder="Washington, DC"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500" />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">Proposed Rate ($/hr)</label>
            <Input type="number" value={proposedRate} onChange={e => setProposedRate(e.target.value)}
              placeholder="125.00" step="0.01"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500" />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <label className="text-sm text-slate-400">Experience Level:</label>
          {['junior', 'mid', 'senior', 'principal'].map(lvl => (
            <label key={lvl} className="flex items-center gap-1.5 cursor-pointer">
              <input type="radio" name="experience" value={lvl}
                checked={experience === lvl} onChange={() => setExperience(lvl)}
                className="border-slate-600" />
              <span className="text-slate-300 text-sm capitalize">{lvl}</span>
            </label>
          ))}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button type="submit" disabled={isLoading || !occupation.trim()} className="bg-green-800 hover:bg-green-700">
            {isLoading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analyzing...</> : 'Analyze Price'}
          </Button>

          {result && !showSaveDialog && (
            <>
              <Button type="button" variant="outline" size="sm"
                onClick={() => { setSaveName(occupation); setShowSaveDialog(true) }}
                className="border-slate-600 text-slate-300 hover:bg-slate-700 flex items-center gap-1.5">
                <Save className="w-4 h-4" />Save
              </Button>
              <Button type="button" variant="outline" size="sm"
                onClick={handleShare}
                className="border-slate-600 text-slate-300 hover:bg-slate-700 flex items-center gap-1.5">
                {copied ? <><Check className="w-4 h-4 text-green-400" />Copied!</> : <><Share2 className="w-4 h-4" />Share</>}
              </Button>
              <Button type="button" variant="outline" size="sm"
                onClick={handleExportCurrent}
                className="border-slate-600 text-slate-300 hover:bg-slate-700 flex items-center gap-1.5">
                <Download className="w-4 h-4" />Export
              </Button>
            </>
          )}

          {showSaveDialog && (
            <div className="flex items-center gap-2">
              <Input value={saveName} onChange={e => setSaveName(e.target.value)}
                placeholder="Analysis name" autoFocus
                onKeyDown={e => { if (e.key === 'Enter') handleSave(false) }}
                className="bg-slate-800 border-slate-600 text-slate-100 h-9 w-52" />
              <Button type="button" size="sm" onClick={() => handleSave(false)}
                className="bg-green-800 hover:bg-green-700 h-9">
                <Save className="w-3.5 h-3.5 mr-1" />Save
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => handleSave(true)}
                className="border-amber-700 text-amber-400 hover:bg-amber-950 h-9">
                <Archive className="w-3.5 h-3.5 mr-1" />Archive
              </Button>
              <button type="button" onClick={() => setShowSaveDialog(false)} className="text-slate-500 hover:text-slate-300">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </form>

      {error && (
        <Card className="bg-red-950 border-red-800">
          <CardContent className="pt-4"><p className="text-red-300 text-sm">{error}</p></CardContent>
        </Card>
      )}

      {result && (
        <div className="space-y-4">
          {result.assessment && (() => {
            const cfg = getAssessmentConfig(result.assessment)
            const Icon = cfg.icon
            return (
              <Card className={`${cfg.bg} border`}>
                <CardContent className="pt-4 flex items-center gap-3">
                  <Icon className={`w-6 h-6 ${cfg.color} flex-shrink-0`} />
                  <div>
                    <p className={`font-semibold ${cfg.color}`}>{cfg.label}</p>
                    <p className="text-slate-300 text-sm">{result.summary}</p>
                  </div>
                </CardContent>
              </Card>
            )
          })()}

          {result.recommended_range_low && result.recommended_range_high && (
            <Card className="bg-slate-800 border-slate-700">
              <CardHeader className="pb-2">
                <CardTitle className="text-slate-200 text-base">Market Rate Range</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <p className="text-slate-500 text-xs">Low</p>
                    <p className="text-slate-300 text-xl font-mono">{fmt(result.recommended_range_low)}</p>
                  </div>
                  <div className="flex-1 h-3 bg-slate-700 rounded-full relative">
                    <div className="absolute inset-y-0 left-[15%] right-[15%] bg-emerald-700 rounded-full" />
                    {result.proposed_price && result.recommended_range_low && result.recommended_range_high && (() => {
                      const range = result.recommended_range_high - result.recommended_range_low
                      const pct = Math.min(100, Math.max(0, ((result.proposed_price - result.recommended_range_low) / range) * 70 + 15))
                      return (
                        <div className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full border-2 border-blue-500 -translate-x-1/2"
                          style={{ left: `${pct}%` }} title={`Proposed: ${fmt(result.proposed_price)}`} />
                      )
                    })()}
                  </div>
                  <div className="text-center">
                    <p className="text-slate-500 text-xs">High</p>
                    <p className="text-slate-300 text-xl font-mono">{fmt(result.recommended_range_high)}</p>
                  </div>
                </div>
                {result.proposed_price && (
                  <p className="text-center text-sm text-blue-400 mt-2">Proposed: {fmt(result.proposed_price)}/hr</p>
                )}
              </CardContent>
            </Card>
          )}

          {result.data_points.length > 0 && (
            <div>
              <h2 className="text-slate-400 text-xs uppercase tracking-wide mb-2">Data Sources</h2>
              <div className="space-y-2">
                {result.data_points.map((dp, idx) => (
                  <Card key={idx} className="bg-slate-800/50 border-slate-700">
                    <CardContent className="pt-3 pb-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-slate-300 text-sm font-medium">{dp.source}</p>
                          <p className="text-slate-500 text-xs">{dp.label}</p>
                          {dp.notes && <p className="text-slate-600 text-xs mt-1">{dp.notes}</p>}
                        </div>
                        <div className="text-right text-xs space-y-0.5">
                          {dp.low    != null && <p className="text-slate-400">Low: <span className="font-mono text-slate-300">{fmt(dp.low)}</span></p>}
                          {dp.median != null && <p className="text-slate-300">Median: <span className="font-mono font-bold">{fmt(dp.median)}</span></p>}
                          {dp.high   != null && <p className="text-slate-400">High: <span className="font-mono text-slate-300">{fmt(dp.high)}</span></p>}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-slate-600">
            Confidence: {result.confidence} | BLS OEWS 2024 (most current). Verify with authoritative sources before award decisions.
          </p>
        </div>
      )}
    </div>
  )
}

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="p-6 text-slate-400">Loading...</div>}>
      <PricingInner />
    </Suspense>
  )
}
