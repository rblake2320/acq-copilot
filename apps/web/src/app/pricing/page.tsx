'use client'

import { useState } from 'react'
import { DollarSign, TrendingUp, TrendingDown, Minus, Loader2, BarChart3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

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
  data_points: PriceDataPoint[]
  recommended_range_low?: number
  recommended_range_high?: number
  proposed_price?: number
  assessment?: string
  confidence: string
  summary: string
}

export default function PricingPage() {
  const [occupation, setOccupation] = useState('')
  const [socCode, setSocCode] = useState('')
  const [location, setLocation] = useState('')
  const [proposedRate, setProposedRate] = useState('')
  const [experience, setExperience] = useState('mid')
  const [result, setResult] = useState<PriceAnalysis | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!occupation.trim()) return
    setIsLoading(true)
    setError(null)

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

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Analysis failed')
      }

      const data = await res.json()
      setResult(data.analysis)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const fmt = (n?: number) => n != null ? `$${n.toFixed(2)}` : 'N/A'

  const getAssessmentConfig = (assessment?: string) => {
    switch (assessment) {
      case 'fair': return { icon: Minus, color: 'text-emerald-400', bg: 'bg-emerald-950/50 border-emerald-800', label: 'Fair Price' }
      case 'high': return { icon: TrendingUp, color: 'text-red-400', bg: 'bg-red-950/50 border-red-800', label: 'Above Market' }
      case 'low': return { icon: TrendingDown, color: 'text-amber-400', bg: 'bg-amber-950/50 border-amber-800', label: 'Below Market' }
      default: return { icon: BarChart3, color: 'text-slate-400', bg: 'bg-slate-800 border-slate-700', label: 'Insufficient Data' }
    }
  }

  return (
    <div className="flex flex-col h-full p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <DollarSign className="w-6 h-6 text-green-400" />
          Price Reasonableness Analyzer
        </h1>
        <p className="text-slate-400 mt-1">
          Cross-source price analysis: BLS OEWS + GSA CALC+ labor rates
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">Occupation / Labor Category</label>
            <Input
              value={occupation}
              onChange={e => setOccupation(e.target.value)}
              placeholder="e.g. Software Developer, Project Manager"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">BLS SOC Code (optional)</label>
            <Input
              value={socCode}
              onChange={e => setSocCode(e.target.value)}
              placeholder="15-1252"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">Location (optional)</label>
            <Input
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="Washington, DC"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">Proposed Rate ($/hr)</label>
            <Input
              type="number"
              value={proposedRate}
              onChange={e => setProposedRate(e.target.value)}
              placeholder="125.00"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
              step="0.01"
            />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <label className="text-sm text-slate-400">Experience Level:</label>
          {['junior', 'mid', 'senior', 'principal'].map(lvl => (
            <label key={lvl} className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="experience"
                value={lvl}
                checked={experience === lvl}
                onChange={() => setExperience(lvl)}
                className="border-slate-600"
              />
              <span className="text-slate-300 text-sm capitalize">{lvl}</span>
            </label>
          ))}
        </div>

        <Button type="submit" disabled={isLoading || !occupation.trim()} className="bg-green-800 hover:bg-green-700">
          {isLoading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analyzing...</> : 'Analyze Price'}
        </Button>
      </form>

      {error && (
        <Card className="bg-red-950 border-red-800">
          <CardContent className="pt-4"><p className="text-red-300 text-sm">{error}</p></CardContent>
        </Card>
      )}

      {result && (
        <div className="space-y-4">
          {/* Assessment banner */}
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

          {/* Price range */}
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
                        <div
                          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full border-2 border-blue-500 -translate-x-1/2"
                          style={{ left: `${pct}%` }}
                          title={`Proposed: ${fmt(result.proposed_price)}`}
                        />
                      )
                    })()}
                  </div>
                  <div className="text-center">
                    <p className="text-slate-500 text-xs">High</p>
                    <p className="text-slate-300 text-xl font-mono">{fmt(result.recommended_range_high)}</p>
                  </div>
                </div>
                {result.proposed_price && (
                  <p className="text-center text-sm text-blue-400 mt-2">
                    Proposed: {fmt(result.proposed_price)}/hr
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Data sources */}
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
                          {dp.low != null && <p className="text-slate-400">Low: <span className="font-mono text-slate-300">{fmt(dp.low)}</span></p>}
                          {dp.median != null && <p className="text-slate-300">Median: <span className="font-mono font-bold">{fmt(dp.median)}</span></p>}
                          {dp.high != null && <p className="text-slate-400">High: <span className="font-mono text-slate-300">{fmt(dp.high)}</span></p>}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-slate-600">
            Confidence: {result.confidence} | Data sourced from BLS OEWS and GSA CALC+. Verify with authoritative sources before award decisions.
          </p>
        </div>
      )}
    </div>
  )
}
