"""IGCE (Independent Government Cost Estimate) Builder orchestration tool."""

from typing import Any
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from app.tools.base import BaseTool, Citation


class IGCEBuilderTool(BaseTool):
    """Tool for building Independent Government Cost Estimates."""

    id = "igce.build"
    name = "IGCE Builder"
    description = "Build comprehensive independent government cost estimates for federal contracts"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["build"], "default": "build"},
            "labor_categories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "soc_code": {"type": "string"},
                        "fte_count": {"type": "number"},
                        "location_code": {"type": "string"}
                    }
                }
            },
            "base_year": {"type": "integer"},
            "option_years": {"type": "integer", "default": 1},
            "productive_hours": {"type": "integer", "default": 1880},
            "burden_multiplier": {"type": "number", "default": 2.0, "minimum": 1.0},
            "escalation_rate": {"type": "number", "default": 0.03},
            "escalation_method": {"type": "string", "enum": ["compound", "simple"], "default": "compound"},
            "travel_events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "destination_city": {"type": "string"},
                        "destination_state": {"type": "string"},
                        "trips_per_year": {"type": "integer"},
                        "nights_per_trip": {"type": "integer"},
                        "travelers": {"type": "integer"}
                    }
                },
                "default": []
            },
            "rounding_rule": {
                "type": "string",
                "enum": ["nearest_dollar", "nearest_cent", "none"],
                "default": "nearest_dollar"
            },
            "scenario": {"type": "string", "enum": ["base", "low", "high"], "default": "base"},
            "low_multiplier": {"type": "number", "default": 0.9},
            "high_multiplier": {"type": "number", "default": 1.1},
            "include_validation": {"type": "boolean", "default": False}
        },
        "required": ["labor_categories", "base_year"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "labor_lines": {"type": "array"},
            "travel_lines": {"type": "array"},
            "yearly_totals": {"type": "object"},
            "grand_total": {"type": "number"},
            "formulas_used": {"type": "array"}
        }
    }
    auth_requirements = []
    rate_limit_profile = {"requests_per_minute": 100}

    async def run(self, params: dict) -> Any:
        """Build IGCE estimate."""
        action = params.get("action", "build").lower()
        
        if action == "build":
            return await self._build_estimate(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _build_estimate(self, params: dict) -> dict:
        """Build complete cost estimate."""
        labor_categories = params.get("labor_categories", [])
        base_year = params.get("base_year") or datetime.utcnow().year
        # Support period_of_performance_years as alias (e.g. 5 years = base + 4 options)
        pop_years = params.get("period_of_performance_years")
        option_years = (pop_years - 1) if pop_years else params.get("option_years", 1)
        productive_hours = params.get("productive_hours", 1880)
        burden_multiplier = params.get("burden_multiplier", 2.0)
        escalation_rate = params.get("escalation_rate", 0.03)
        escalation_method = params.get("escalation_method", "compound")
        travel_events = params.get("travel_events", [])
        rounding_rule = params.get("rounding_rule", "nearest_dollar")
        scenario = params.get("scenario", "base")
        low_multiplier = params.get("low_multiplier", 0.9)
        high_multiplier = params.get("high_multiplier", 1.1)
        include_validation = params.get("include_validation", False)
        
        labor_lines = []
        travel_lines = []
        validation_lines = []
        yearly_totals = {}
        formulas = []
        
        # Initialize yearly totals
        for year in range(base_year, base_year + option_years + 1):
            yearly_totals[year] = {"labor": 0.0, "travel": 0.0, "total": 0.0}
        
        # Process labor categories
        for labor_cat in labor_categories:
            # Look up BLS wage (mock implementation)
            base_hourly = await self._lookup_bls_wage(labor_cat["soc_code"], labor_cat["location_code"])
            
            # Convert to annual
            annual_rate = base_hourly * productive_hours
            
            # Apply burden multiplier
            burdened_rate = annual_rate * burden_multiplier
            formula = f"burdened_rate = {base_hourly:.2f}/hr × {productive_hours} hrs × {burden_multiplier}"
            formulas.append(formula)
            
            # Calculate costs by year
            years_costs = {}
            for i in range(option_years + 1):
                year = base_year + i
                
                if escalation_method == "compound":
                    escalation_factor = (1 + escalation_rate) ** i
                else:  # simple
                    escalation_factor = 1 + (escalation_rate * i)
                
                escalated_rate = burdened_rate * escalation_factor
                annual_cost = escalated_rate * labor_cat["fte_count"]
                
                years_costs[year] = self._round_value(annual_cost, rounding_rule)
                yearly_totals[year]["labor"] += years_costs[year]
            
            labor_lines.append({
                "category": labor_cat["title"],
                "soc_code": labor_cat["soc_code"],
                "location": labor_cat["location_code"],
                "base_rate": annual_rate,
                "burdened_rate": burdened_rate,
                "annual_cost": years_costs[base_year],
                "years": years_costs
            })
            
            # Validation against CALC+ (if requested)
            if include_validation:
                calc_ceiling = await self._lookup_calc_ceiling(labor_cat["title"])
                validation_lines.append({
                    "category": labor_cat["title"],
                    "bls_rate": annual_rate,
                    "calc_ceiling": calc_ceiling,
                    "within_range": burdened_rate <= calc_ceiling
                })
        
        # Process travel events
        for travel in travel_events:
            # Look up per diem (mock implementation)
            per_diem = await self._lookup_per_diem(travel["destination_city"], travel["destination_state"], base_year)
            
            lodging = per_diem * 0.6
            mie = per_diem * 0.4
            
            years_costs = {}
            annual_per_event = (lodging + mie) * travel["nights_per_trip"]
            annual_travel_cost = annual_per_event * travel["trips_per_year"] * travel["travelers"]
            
            for i in range(option_years + 1):
                year = base_year + i
                
                if escalation_method == "compound":
                    escalation_factor = (1 + escalation_rate) ** i
                else:
                    escalation_factor = 1 + (escalation_rate * i)
                
                escalated_cost = annual_travel_cost * escalation_factor
                years_costs[year] = self._round_value(escalated_cost, rounding_rule)
                yearly_totals[year]["travel"] += years_costs[year]
            
            travel_lines.append({
                "destination": f"{travel['destination_city']}, {travel['destination_state']}",
                "per_diem_rate": per_diem,
                "lodging": lodging,
                "mie": mie,
                "trips": travel["trips_per_year"],
                "nights": travel["nights_per_trip"],
                "travelers": travel["travelers"],
                "annual_cost": years_costs[base_year],
                "years": years_costs
            })
        
        # Calculate totals
        grand_total = 0.0
        for year in yearly_totals:
            yearly_totals[year]["total"] = self._round_value(
                yearly_totals[year]["labor"] + yearly_totals[year]["travel"],
                rounding_rule
            )
            grand_total += yearly_totals[year]["total"]
        
        # Handle scenario multipliers
        sensitivity = None
        if scenario == "low":
            sensitivity_value = grand_total * low_multiplier
            sensitivity = {
                "low": self._round_value(sensitivity_value, rounding_rule),
                "base": grand_total,
                "high": self._round_value(grand_total * high_multiplier, rounding_rule)
            }
            grand_total = sensitivity["low"]
        elif scenario == "high":
            sensitivity_value = grand_total * high_multiplier
            sensitivity = {
                "low": self._round_value(grand_total * low_multiplier, rounding_rule),
                "base": grand_total,
                "high": self._round_value(sensitivity_value, rounding_rule)
            }
            grand_total = sensitivity["high"]
        else:  # base
            sensitivity = {
                "low": self._round_value(grand_total * low_multiplier, rounding_rule),
                "base": grand_total,
                "high": self._round_value(grand_total * high_multiplier, rounding_rule)
            }
        
        return {
            "labor_lines": labor_lines,
            "travel_lines": travel_lines,
            "validation_lines": validation_lines if validation_lines else None,
            "yearly_totals": yearly_totals,
            "grand_total": self._round_value(grand_total, rounding_rule),
            "assumptions": {
                "base_year": base_year,
                "option_years": option_years,
                "productive_hours_per_fte": productive_hours,
                "burden_multiplier": burden_multiplier,
                "escalation_rate": f"{escalation_rate * 100}%",
                "escalation_method": escalation_method,
                "scenario": scenario,
            },
            "formulas_used": formulas,
            "sensitivity": sensitivity
        }

    async def _lookup_bls_wage(self, soc_code: str, area_code: str) -> float:
        """Mock BLS wage lookup - returns hourly rate."""
        mock_wages = {
            "11-1011": 89.5,
            "11-2011": 60.0,
            "13-1111": 45.5,
            "15-1121": 57.5,
        }
        return mock_wages.get(soc_code, 48.0)

    async def _lookup_per_diem(self, city: str, state: str, year: int) -> float:
        """Mock GSA per diem lookup - returns daily rate."""
        mock_rates = {
            ("Washington", "DC"): 330.0,
            ("New York", "NY"): 340.0,
            ("San Francisco", "CA"): 320.0,
        }
        return mock_rates.get((city, state), 200.0)

    async def _lookup_calc_ceiling(self, labor_category: str) -> float:
        """Mock CALC+ ceiling lookup - returns hourly ceiling."""
        return 300.0

    @staticmethod
    def _round_value(value: float, rounding_rule: str) -> float:
        """Apply rounding rule to a value."""
        if rounding_rule == "nearest_dollar":
            return float(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        elif rounding_rule == "nearest_cent":
            return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:  # none
            return value

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for IGCE estimate."""
        citations = []
        
        citations.append(Citation(
            source_name="BLS OEWS",
            source_url="https://www.bls.gov/oes/",
            source_label="BLS Occupational Employment and Wage Statistics",
            retrieved_at=datetime.utcnow()
        ))
        
        citations.append(Citation(
            source_name="GSA Per Diem",
            source_url="https://www.gsa.gov/travel/plan-book/per-diem-rates/",
            source_label="GSA Per Diem Rates",
            retrieved_at=datetime.utcnow()
        ))
        
        citations.append(Citation(
            source_name="GSA CALC+",
            source_url="https://www.gsa.gov/about-us/divisions-offices/federal-acquisition-service/calc",
            source_label="GSA CALC+ Schedule Rates",
            retrieved_at=datetime.utcnow()
        ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """IGCE Builder is local computation, always healthy."""
        return {
            "tool_id": self.id,
            "status": "healthy",
            "message": "IGCE Builder is fully operational (local computation)"
        }

    def get_examples(self) -> list[dict]:
        """Return example invocations."""
        return [
            {
                "action": "build",
                "labor_categories": [
                    {
                        "title": "Project Manager",
                        "soc_code": "11-2011",
                        "fte_count": 1.0,
                        "location_code": "US000000"
                    },
                    {
                        "title": "Software Developer",
                        "soc_code": "15-1121",
                        "fte_count": 3.0,
                        "location_code": "US000000"
                    }
                ],
                "base_year": 2024,
                "option_years": 2,
                "burden_multiplier": 1.95,
                "escalation_rate": 0.025,
                "travel_events": [
                    {
                        "destination_city": "Washington",
                        "destination_state": "DC",
                        "trips_per_year": 2,
                        "nights_per_trip": 2,
                        "travelers": 2
                    }
                ]
            }
        ]
