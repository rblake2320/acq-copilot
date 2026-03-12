'use client'

import { useState } from 'react'
import { MapPin, DollarSign, Zap, Building2, ExternalLink, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface ThresholdInfo {
  name: string
  value: number
  far_reference: string
  description: string
  requirements: string[]
}

interface VehicleRecommendation {
  vehicle_name: string
  vehicle_type: string
  managing_agency: string
  description: string
  best_for: string[]
  ceiling?: string
  small_business_options: boolean
  url: string
  pros: string[]
  cons: string[]
}

interface StrategyResult {
  requirement: string
  estimated_value?: number
  thresholds: {
    applicable: ThresholdInfo[]
    summary: string
  }
  vehicles: {
    recommendations: VehicleRecommendation[]
    procurement_approach: string
    reasoning: string
  }
}

export default function PlanningPage() {
  const [description, setDescription] = useState('')
  const [value, setValue] = useState('')
  const [naics, setNaics] = useState('')
  const [sbPref, setSbPref] = useState(false)
  const [agencyType, setAgencyType] = useState('civilian')
  const [result, setResult] = useState<StrategyResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedVehicle, setExpandedVehicle] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim()) return
    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/planning/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: description.trim(),
          estimated_value: value ? parseInt(value.replace(/,/g, '')) : null,
          naics_code: naics || null,
          small_business_preference: sbPref,
          agency_type: agencyType,
        }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Strategy generation failed')
      }

      setResult(await res.json())
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const formatCurrency = (val: number) => {
    if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`
    if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`
    return `$${val}`
  }

  return (
    <div className="flex flex-col h-full p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Zap className="w-6 h-6 text-yellow-400" />
          Acquisition Planning Assistant
        </h1>
        <p className="text-slate-400 mt-1">
          Describe your requirement — get vehicle recommendations and threshold analysis
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="text-sm text-slate-400 mb-1.5 block">What do you need to buy?</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="e.g. Cloud hosting services for a web application, cybersecurity assessment, IT project management support..."
            className="w-full h-24 bg-slate-800 border border-slate-600 text-slate-200 rounded-lg p-3 text-sm resize-none placeholder:text-slate-500 focus:outline-none focus:border-yellow-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">Estimated Value ($)</label>
            <Input
              value={value}
              onChange={e => setValue(e.target.value)}
              placeholder="250000"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1.5 block">NAICS Code</label>
            <Input
              value={naics}
              onChange={e => setNaics(e.target.value)}
              placeholder="541511"
              className="bg-slate-800 border-slate-600 text-slate-100 placeholder:text-slate-500"
            />
          </div>
        </div>

        <div className="flex gap-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={sbPref}
              onChange={e => setSbPref(e.target.checked)}
              className="rounded border-slate-600"
            />
            <span className="text-slate-300 text-sm">Small Business preference</span>
          </label>
          <div className="flex gap-3">
            {['civilian', 'dod'].map(type => (
              <label key={type} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="agencyType"
                  value={type}
                  checked={agencyType === type}
                  onChange={() => setAgencyType(type)}
                  className="border-slate-600"
                />
                <span className="text-slate-300 text-sm capitalize">{type === 'dod' ? 'DoD' : 'Civilian'}</span>
              </label>
            ))}
          </div>
        </div>

        <Button type="submit" disabled={isLoading || !description.trim()} className="bg-yellow-700 hover:bg-yellow-600 text-white">
          {isLoading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analyzing...</> : 'Generate Strategy'}
        </Button>
      </form>

      {error && (
        <Card className="bg-red-950 border-red-800">
          <CardContent className="pt-4"><p className="text-red-300 text-sm">{error}</p></CardContent>
        </Card>
      )}

      {result && (
        <div className="space-y-6">
          {/* Procurement approach */}
          <Card className="bg-yellow-950/30 border-yellow-800">
            <CardContent className="pt-4">
              <p className="text-yellow-300 font-medium">Recommended Approach</p>
              <p className="text-slate-300 text-sm mt-1">{result.vehicles.procurement_approach}</p>
              <p className="text-slate-500 text-xs mt-1">{result.vehicles.reasoning}</p>
            </CardContent>
          </Card>

          {/* Thresholds */}
          {result.thresholds.applicable.length > 0 && (
            <div>
              <h2 className="text-slate-300 font-semibold text-sm uppercase tracking-wide mb-3">
                Applicable Thresholds
              </h2>
              <p className="text-slate-400 text-sm mb-3">{result.thresholds.summary}</p>
              <div className="space-y-2">
                {result.thresholds.applicable.map((t, idx) => (
                  <Card key={idx} className="bg-slate-800 border-slate-700">
                    <CardContent className="pt-3 pb-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-slate-200 text-sm font-medium">{t.name}</span>
                            <Badge variant="outline" className="font-mono text-xs border-slate-600 text-slate-400">
                              {formatCurrency(t.value)}
                            </Badge>
                          </div>
                          <p className="text-slate-400 text-xs mt-1">{t.description}</p>
                          <p className="text-blue-400 text-xs mt-1">{t.far_reference}</p>
                        </div>
                      </div>
                      <ul className="mt-2 space-y-0.5">
                        {t.requirements.map((req, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-xs text-slate-400">
                            <CheckCircle2 className="w-3 h-3 text-emerald-500 flex-shrink-0 mt-0.5" />
                            {req}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Vehicle recommendations */}
          {result.vehicles.recommendations.length > 0 && (
            <div>
              <h2 className="text-slate-300 font-semibold text-sm uppercase tracking-wide mb-3">
                Contract Vehicle Recommendations
              </h2>
              <div className="space-y-3">
                {result.vehicles.recommendations.map((v, idx) => (
                  <Card key={idx} className="bg-slate-800 border-slate-700">
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            {idx === 0 && <Badge className="bg-yellow-900 text-yellow-300 text-xs">Top Pick</Badge>}
                            <Badge variant="outline" className="text-xs border-slate-600 text-slate-400">{v.vehicle_type}</Badge>
                            {v.small_business_options && <Badge className="bg-emerald-900 text-emerald-300 text-xs">SB Available</Badge>}
                          </div>
                          <CardTitle className="text-slate-100 text-base">{v.vehicle_name}</CardTitle>
                          <p className="text-slate-500 text-xs">Managed by {v.managing_agency}{v.ceiling ? ` · Ceiling: ${v.ceiling}` : ''}</p>
                        </div>
                        <a href={v.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-slate-300 text-sm">{v.description}</p>
                      <button
                        onClick={() => setExpandedVehicle(expandedVehicle === v.vehicle_name ? null : v.vehicle_name)}
                        className="text-xs text-blue-400 hover:text-blue-300 mt-2"
                      >
                        {expandedVehicle === v.vehicle_name ? 'Hide details ↑' : 'Show pros/cons ↓'}
                      </button>
                      {expandedVehicle === v.vehicle_name && (
                        <div className="mt-3 grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-xs text-emerald-400 font-medium mb-1">Pros</p>
                            {v.pros.map((p, i) => <p key={i} className="text-xs text-slate-400">✓ {p}</p>)}
                          </div>
                          <div>
                            <p className="text-xs text-red-400 font-medium mb-1">Cons</p>
                            {v.cons.map((c, i) => <p key={i} className="text-xs text-slate-400">✗ {c}</p>)}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
