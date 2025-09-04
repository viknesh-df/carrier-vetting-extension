from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Dict, Any, List
from opentelemetry import trace
import json
import time
import httpx
import os
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()



# Initialize tracer
tracer = trace.get_tracer(__name__)

# FMCSA API configuration
FMCSA_BASE_URL = os.getenv("FMCSA_BASE_URL")
FMCSA_WEB_KEY = os.getenv("FMCSA_WEB_KEY")

# Endpoint paths to fetch
FMCSA_ENDPOINTS = {
    "basics": "/basics",
    "cargo_carried": "/cargo-carried", 
    "operation_classification": "/operation-classification",
    "docket_numbers": "/docket-numbers",
    "authority": "/authority"
}

class CarrierVettingState(TypedDict):
    messages: List[Dict[str, Any]]
    current_step: str
    input_data: Dict[str, Any]
    dot_number: str
    fmcsa_data: Dict[str, Any]
    additional_data: Dict[str, Any]
    carrier_info: Dict[str, Any]
    safety_analysis: Dict[str, Any]
    insurance_analysis: Dict[str, Any]
    authority_analysis: Dict[str, Any]
    company_analysis: Dict[str, Any]
    recommendation: Dict[str, Any]
    formatted_response: Dict[str, Any]
    error: str
    execution_time_ms: int
    tenant_id: str
    user_id: str

def validate_input(state: CarrierVettingState) -> CarrierVettingState:
    """Validate input data for carrier vetting"""
    with tracer.start_as_current_span("validate_input") as span:
        span.set_attribute("agent_id", "carrier_vetting")
        span.set_attribute("step", "validate_input")
        
        try:
            # The input can come in multiple formats:
            # 1. Direct input: {"dot": "1234567"}
            # 2. Nested input: {"input_data": {"dot": "1234567"}}
            # 3. Lead format: {"lead": {"dot": "1234567"}}
            
            input_data = state.get("input_data", {})
            
            # If input_data is empty, try to get from the root level
            if not input_data:
                # Check if the input is at the root level
                root_input = {k: v for k, v in state.items() if k not in ["messages", "current_step", "fmcsa_data", "additional_data", "carrier_info", "safety_analysis", "insurance_analysis", "authority_analysis", "company_analysis", "recommendation", "formatted_response", "error", "execution_time_ms", "tenant_id", "user_id", "_start_time", "dot_number"]}
                if root_input:
                    input_data = root_input
                    state["input_data"] = input_data
            
            span.set_attribute("input_data_keys", list(input_data.keys()))
            
            # Check for lead format and extract dot number
            dot_number = None
            
            # Try to get from lead object first
            if "lead" in input_data and isinstance(input_data["lead"], dict):
                lead_data = input_data["lead"]
                dot_number = lead_data.get("dot")
                span.set_attribute("found_in_lead", True)
            else:
                # Try direct access
                dot_number = input_data.get("dot")
                span.set_attribute("found_in_lead", False)
            
            span.set_attribute("dot_number_found", dot_number is not None)
            
            # Validate required fields
            if not dot_number:
                state["error"] = "DOT number is required"
                state["current_step"] = "error"
                span.set_attribute("error", state["error"])
                return state
            
            # Validate field types
            if not isinstance(dot_number, str):
                state["error"] = "DOT number must be a string"
                state["current_step"] = "error"
                span.set_attribute("error", state["error"])
                return state
            
            # Clean and validate DOT number
            dot_number = str(dot_number).strip()
            if not dot_number.isdigit():
                state["error"] = "DOT number must contain only digits"
                state["current_step"] = "error"
                span.set_attribute("error", state["error"])
                return state
            
            # Update state with validated data
            state["dot_number"] = dot_number
            input_data["dot"] = dot_number
            state["input_data"] = input_data
            
            # Check if mock mode is requested
            mock_mode = input_data.get("mock", False)
            span.set_attribute("mock_mode", mock_mode)
            
            state["current_step"] = "fetch_fmcsa_data"
            span.set_attribute("validation_success", True)
            
        except Exception as e:
            state["error"] = f"Validation error: {str(e)}"
            state["current_step"] = "error"
            span.set_attribute("error", state["error"])
        
        return state

def fetch_fmcsa_data(state: CarrierVettingState) -> CarrierVettingState:
    """Fetch data from FMCSA API"""
    with tracer.start_as_current_span("fetch_fmcsa_data") as span:
        span.set_attribute("agent_id", "carrier_vetting")
        span.set_attribute("step", "fetch_fmcsa_data")
        
        try:
            dot_number = state["dot_number"]
            mock_mode = state["input_data"].get("mock", False)
            
            span.set_attribute("dot_number", dot_number)
            span.set_attribute("mock_mode", mock_mode)
            
            if mock_mode:
                # Return mock data
                state["fmcsa_data"] = {
                    "content": {
                        "carrier": {
                            "legalName": "SAMPLE CARRIER INC",
                            "dbaName": "SAMPLE LOGISTICS",
                            "dotNumber": int(dot_number),
                            "totalDrivers": 15,
                            "totalPowerUnits": 12
                        }
                    }
                }
                state["additional_data"] = {}
                state["current_step"] = "analyze_data"
                span.set_attribute("mock_data_used", True)
                return state
            
            # Fetch main carrier data
            main_data = _fetch_fmcsa_data(dot_number)
            print(main_data)
            if not main_data or not isinstance(main_data, dict):
                state["error"] = f"Failed to fetch FMCSA data for DOT {dot_number}"
                state["current_step"] = "error"
                span.set_attribute("error", state["error"])
                return state
            
            state["fmcsa_data"] = main_data
            
            # Fetch additional endpoint data (tolerate failures per endpoint)
            additional_data = {}
            for endpoint_name, endpoint_path in FMCSA_ENDPOINTS.items():
                try:
                    data = _fetch_fmcsa_data(dot_number, endpoint_path)
                    if isinstance(data, dict):
                        additional_data[endpoint_name] = data
                        span.set_attribute(f"endpoint_{endpoint_name}_success", True)
                    else:
                        span.set_attribute(f"endpoint_{endpoint_name}_success", False)
                except Exception as e:
                    span.set_attribute(f"endpoint_{endpoint_name}_success", False)
                    span.set_attribute(f"endpoint_{endpoint_name}_error", str(e))
                    continue
            
            state["additional_data"] = additional_data
            state["current_step"] = "analyze_data"
            
            span.set_attribute("main_data_fetched", True)
            span.set_attribute("additional_endpoints_fetched", len(additional_data))
            span.set_attribute("fetch_success", True)
            
        except Exception as e:
            state["error"] = f"FMCSA data fetch error: {str(e)}"
            state["current_step"] = "error"
            span.set_attribute("error", state["error"])
        
        return state

def analyze_data(state: CarrierVettingState) -> CarrierVettingState:
    """Analyze FMCSA data and perform comprehensive vetting"""
    with tracer.start_as_current_span("analyze_data") as span:
        span.set_attribute("agent_id", "carrier_vetting")
        span.set_attribute("step", "analyze_data")
        
        try:
            fmcsa_data = state["fmcsa_data"]
            additional_data = state["additional_data"]
            
            # Extract carrier data
            carrier_data = (fmcsa_data.get("content") or {})
            carrier = (carrier_data.get("carrier") or {})
            
            if not carrier:
                state["error"] = f"No carrier data found for DOT {state['dot_number']}"
                state["current_step"] = "error"
                span.set_attribute("error", state["error"])
                return state
            
            # Extract carrier info
            state["carrier_info"] = {
                "legal_name": carrier.get("legalName"),
                "dba_name": carrier.get("dbaName"),
                "dot_number": carrier.get("dotNumber"),
                "ein": carrier.get("ein"),
                "address": {
                    "street": carrier.get("phyStreet"),
                    "city": carrier.get("phyCity"),
                    "state": carrier.get("phyState"),
                    "zipcode": carrier.get("phyZipcode"),
                    "country": carrier.get("phyCountry")
                }
            }
            
            # Perform comprehensive analysis
            try:
                state["safety_analysis"] = _analyze_safety_metrics(fmcsa_data)
                span.set_attribute("safety_analysis_success", True)
            except Exception as exc:
                state["safety_analysis"] = {"error": f"safety_analysis_failed: {exc}"}
                span.set_attribute("safety_analysis_success", False)
                span.set_attribute("safety_analysis_error", str(exc))
            
            try:
                state["insurance_analysis"] = _analyze_insurance_compliance(fmcsa_data)
                span.set_attribute("insurance_analysis_success", True)
            except Exception as exc:
                state["insurance_analysis"] = {"error": f"insurance_analysis_failed: {exc}", "fully_compliant": False, "insurance_score": 0}
                span.set_attribute("insurance_analysis_success", False)
                span.set_attribute("insurance_analysis_error", str(exc))
            
            try:
                state["authority_analysis"] = _analyze_authority_status(fmcsa_data, additional_data.get("authority"))
                span.set_attribute("authority_analysis_success", True)
            except Exception as exc:
                state["authority_analysis"] = {"error": f"authority_analysis_failed: {exc}", "authority_active": False, "authority_score": 0}
                span.set_attribute("authority_analysis_success", False)
                span.set_attribute("authority_analysis_error", str(exc))
            
            try:
                state["company_analysis"] = _analyze_company_profile(fmcsa_data)
                span.set_attribute("company_analysis_success", True)
            except Exception as exc:
                state["company_analysis"] = {"error": f"company_analysis_failed: {exc}", "company_score": 0}
                span.set_attribute("company_analysis_success", False)
                span.set_attribute("company_analysis_error", str(exc))
            
            state["current_step"] = "generate_recommendation"
            span.set_attribute("analysis_success", True)
            
        except Exception as e:
            state["error"] = f"Analysis error: {str(e)}"
            state["current_step"] = "error"
            span.set_attribute("error", state["error"])
        
        return state

def generate_recommendation(state: CarrierVettingState) -> CarrierVettingState:
    """Generate final recommendation based on analysis"""
    with tracer.start_as_current_span("generate_recommendation") as span:
        span.set_attribute("agent_id", "carrier_vetting")
        span.set_attribute("step", "generate_recommendation")
        
        try:
            safety_analysis = state["safety_analysis"]
            insurance_analysis = state["insurance_analysis"]
            authority_analysis = state["authority_analysis"]
            company_analysis = state["company_analysis"]
            
            # Generate recommendation
            state["recommendation"] = _generate_recommendation(
                safety_analysis, 
                insurance_analysis, 
                authority_analysis, 
                company_analysis
            )
            
            state["current_step"] = "format_response"
            span.set_attribute("recommendation_success", True)
            
        except Exception as e:
            state["error"] = f"Recommendation error: {str(e)}"
            state["current_step"] = "error"
            span.set_attribute("error", state["error"])
        
        return state

def format_response(state: CarrierVettingState) -> CarrierVettingState:
    """Format the final response"""
    with tracer.start_as_current_span("format_response") as span:
        span.set_attribute("agent_id", "carrier_vetting")
        span.set_attribute("step", "format_response")
        
        try:
            dot_number = state["dot_number"]
            fmcsa_data = state["fmcsa_data"]
            additional_data = state["additional_data"]
            carrier_info = state["carrier_info"]
            safety_analysis = state["safety_analysis"]
            insurance_analysis = state["insurance_analysis"]
            authority_analysis = state["authority_analysis"]
            company_analysis = state["company_analysis"]
            recommendation = state["recommendation"]
            
            # Determine source
            source = "fmcsa_mock" if state["input_data"].get("mock", False) else "fmcsa_api"
            
            state["formatted_response"] = {
                "dot": dot_number,
                "source": source,
                "retrieval_date": fmcsa_data.get("retrievalDate", datetime.now().isoformat()),
                "carrier_info": carrier_info,
                "analysis": {
                    "company_profile": company_analysis,
                    "safety_metrics": safety_analysis,
                    "insurance_compliance": insurance_analysis,
                    "authority_status": authority_analysis
                },
                "recommendation": recommendation,
                "evidence": {
                    "raw_data": fmcsa_data,
                    "additional_endpoints": additional_data
                },
                "context": {
                    "tenant": state.get("tenant_id"),
                    "user": state.get("user_id"),
                    "execution_time_ms": state.get("execution_time_ms", 0),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            state["current_step"] = "end"
            span.set_attribute("format_success", True)
            
        except Exception as e:
            state["error"] = f"Format error: {str(e)}"
            state["current_step"] = "error"
            span.set_attribute("error", state["error"])
        
        return state

def handle_error(state: CarrierVettingState) -> CarrierVettingState:
    """Handle errors in the workflow"""
    with tracer.start_as_current_span("handle_error") as span:
        span.set_attribute("agent_id", "carrier_vetting")
        span.set_attribute("step", "handle_error")
        
        error = state.get("error", "Unknown error")
        span.set_attribute("error_message", error)
        
        state["formatted_response"] = {
            "error": error,
            "dot": state.get("dot_number", "unknown"),
            "context": {
                "tenant": state.get("tenant_id"),
                "user": state.get("user_id"),
                "execution_time_ms": state.get("execution_time_ms", 0),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        return state

# Helper functions (copied from original agent)
def _fetch_fmcsa_data(dot_number: str, endpoint: str = "") -> Dict[str, Any]:
    """Fetch data from FMCSA API endpoint"""
    try:
        url = f"{FMCSA_BASE_URL}/{dot_number}{endpoint}?webKey={FMCSA_WEB_KEY}"
        print(f"Fetching URL: {url}")  # 👈 Debug print
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            print(f"Status {response.status_code}")  # 👈 Debug print
            return response.json()
    except Exception as e:
        print(f"FMCSA fetch failed: {e}")  # 👈 Show the real error
        return None


def _analyze_safety_metrics(carrier_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze safety metrics and compare with national averages"""
    content = (carrier_data or {}).get("content") or {}
    carrier = (content.get("carrier") or {})
    
    # Extract metrics
    driver_oos_rate = float(carrier.get("driverOosRate", 0))
    vehicle_oos_rate = float(carrier.get("vehicleOosRate", 0))
    hazmat_oos_rate = float(carrier.get("hazmatOosRate", 0))
    
    # National averages
    driver_oos_national = float(carrier.get("driverOosRateNationalAverage", 5.51))
    vehicle_oos_national = float(carrier.get("vehicleOosRateNationalAverage", 20.72))
    hazmat_oos_national = float(carrier.get("hazmatOosRateNationalAverage", 4.5))
    
    # Crash data
    total_crashes = int(carrier.get("crashTotal", 0))
    fatal_crashes = int(carrier.get("fatalCrash", 0))
    injury_crashes = int(carrier.get("injCrash", 0))
    towaway_crashes = int(carrier.get("towawayCrash", 0))
    
    # Safety rating
    safety_rating = carrier.get("safetyRating", "Unknown")
    safety_rating_date = carrier.get("safetyRatingDate")
    
    # Calculate safety scores (0-100, higher is better)
    driver_safety_score = max(0, 100 - (driver_oos_rate / driver_oos_national * 50)) if driver_oos_national > 0 else 100
    vehicle_safety_score = max(0, 100 - (vehicle_oos_rate / vehicle_oos_national * 50)) if vehicle_oos_national > 0 else 100
    hazmat_safety_score = max(0, 100 - (hazmat_oos_rate / hazmat_oos_national * 50)) if hazmat_oos_national > 0 else 100
    
    # Overall safety score
    overall_safety_score = round((driver_safety_score + vehicle_safety_score + hazmat_safety_score) / 3, 1)
    
    return {
        "driver_oos_rate": driver_oos_rate,
        "driver_oos_national_avg": driver_oos_national,
        "driver_safety_score": round(driver_safety_score, 1),
        "vehicle_oos_rate": vehicle_oos_rate,
        "vehicle_oos_national_avg": vehicle_oos_national,
        "vehicle_safety_score": round(vehicle_safety_score, 1),
        "hazmat_oos_rate": hazmat_oos_rate,
        "hazmat_oos_national_avg": hazmat_oos_national,
        "hazmat_safety_score": round(hazmat_safety_score, 1),
        "total_crashes": total_crashes,
        "fatal_crashes": fatal_crashes,
        "injury_crashes": injury_crashes,
        "towaway_crashes": towaway_crashes,
        "safety_rating": safety_rating,
        "safety_rating_date": safety_rating_date,
        "overall_safety_score": overall_safety_score
    }

def _analyze_insurance_compliance(carrier_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze insurance compliance"""
    content = (carrier_data or {}).get("content") or {}
    carrier = (content.get("carrier") or {})
    
    # Insurance requirements and amounts
    bipd_required = carrier.get("bipdInsuranceRequired") == "Y"
    bipd_required_amount = float(carrier.get("bipdRequiredAmount", 0))
    bipd_on_file = float(carrier.get("bipdInsuranceOnFile", 0))
    
    bond_required = carrier.get("bondInsuranceRequired") == "Y"
    bond_on_file = float(carrier.get("bondInsuranceOnFile", 0))
    
    cargo_required = carrier.get("cargoInsuranceRequired") == "Y"
    cargo_on_file = float(carrier.get("cargoInsuranceOnFile", 0))
    
    # Calculate compliance
    bipd_compliant = not bipd_required or bipd_on_file >= bipd_required_amount
    bond_compliant = not bond_required or bond_on_file > 0
    cargo_compliant = not cargo_required or cargo_on_file > 0
    
    fully_compliant = bipd_compliant and bond_compliant and cargo_compliant
    
    # Calculate insurance score (0-100)
    compliance_count = sum([bipd_compliant, bond_compliant, cargo_compliant])
    total_requirements = sum([bipd_required, bond_required, cargo_required])
    insurance_score = (compliance_count / max(total_requirements, 1)) * 100 if total_requirements > 0 else 100
    
    return {
        "bipd_required": bipd_required,
        "bipd_required_amount": bipd_required_amount,
        "bipd_on_file": bipd_on_file,
        "bipd_compliant": bipd_compliant,
        "bond_required": bond_required,
        "bond_on_file": bond_on_file,
        "bond_compliant": bond_compliant,
        "cargo_required": cargo_required,
        "cargo_on_file": cargo_on_file,
        "cargo_compliant": cargo_compliant,
        "fully_compliant": fully_compliant,
        "insurance_score": round(insurance_score, 1)
    }

def _analyze_authority_status(carrier_data: Dict[str, Any], authority_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Analyze authority status"""
    content = (carrier_data or {}).get("content") or {}
    carrier = (content.get("carrier") or {})
    
    # Basic authority info
    authority_status = carrier.get("operatingStatus", "Unknown")
    authority_active = authority_status == "A"
    
    # Authority score (100 if active, 0 if not)
    authority_score = 100 if authority_active else 0
    
    return {
        "authority_status": authority_status,
        "authority_active": authority_active,
        "authority_score": authority_score
    }

def _analyze_company_profile(carrier_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze company profile"""
    content = (carrier_data or {}).get("content") or {}
    carrier = (content.get("carrier") or {})
    
    # Company metrics
    total_drivers = int(carrier.get("totalDrivers", 0))
    total_power_units = int(carrier.get("totalPowerUnits", 0))
    
    # Company score based on size and completeness
    company_score = 0
    
    # Score for having drivers and power units
    if total_drivers > 0:
        company_score += 30
    if total_power_units > 0:
        company_score += 30
    
    # Score for having complete information
    if carrier.get("legalName"):
        company_score += 20
    if carrier.get("phyStreet") and carrier.get("phyCity"):
        company_score += 20
    
    return {
        "total_drivers": total_drivers,
        "total_power_units": total_power_units,
        "company_score": min(100, company_score)
    }

def _generate_recommendation(safety_analysis: Dict[str, Any], insurance_analysis: Dict[str, Any], 
                           authority_analysis: Dict[str, Any], company_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate final recommendation"""
    # Extract scores
    safety_score = safety_analysis.get("overall_safety_score", 0)
    insurance_score = insurance_analysis.get("insurance_score", 0)
    authority_score = authority_analysis.get("authority_score", 0)
    company_score = company_analysis.get("company_score", 0)
    
    # Calculate overall score
    overall_score = round((safety_score + insurance_score + authority_score + company_score) / 4, 1)
    
    # Determine risk level
    if overall_score >= 80:
        risk_level = "LOW"
        recommendation = "APPROVED"
        confidence = "HIGH"
    elif overall_score >= 60:
        risk_level = "MEDIUM"
        recommendation = "APPROVED_WITH_CONDITIONS"
        confidence = "MEDIUM"
    else:
        risk_level = "HIGH"
        recommendation = "REJECTED"
        confidence = "HIGH"
    
    # Generate concerns and positives
    concerns = []
    positives = []
    
    if safety_score < 70:
        concerns.append("Low safety score")
    else:
        positives.append("Good safety record")
    
    if not insurance_analysis.get("fully_compliant", False):
        concerns.append("Insurance compliance issues")
    else:
        positives.append("Fully compliant with insurance requirements")
    
    if not authority_analysis.get("authority_active", False):
        concerns.append("Inactive authority status")
    else:
        positives.append("Active authority status")
    
    if company_score < 50:
        concerns.append("Incomplete company profile")
    else:
        positives.append("Complete company profile")
    
    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "confidence": confidence,
        "concerns": concerns,
        "positives": positives,
        "score_breakdown": {
            "safety": safety_score,
            "insurance": insurance_score,
            "authority": authority_score,
            "company": company_score
        }
    }

def create_carrier_vetting_graph():
    """Create the carrier vetting workflow graph"""
    workflow = StateGraph(CarrierVettingState)
    
    # Add nodes
    workflow.add_node("validate_input", validate_input)
    workflow.add_node("fetch_fmcsa_data", fetch_fmcsa_data)
    workflow.add_node("analyze_data", analyze_data)
    workflow.add_node("generate_recommendation", generate_recommendation)
    workflow.add_node("format_response", format_response)
    workflow.add_node("handle_error", handle_error)
    
    # Set entry point
    workflow.set_entry_point("validate_input")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "validate_input",
        lambda state: "fetch_fmcsa_data" if state.get("current_step") == "fetch_fmcsa_data" else "handle_error"
    )
    
    workflow.add_conditional_edges(
        "fetch_fmcsa_data",
        lambda state: "analyze_data" if state.get("current_step") == "analyze_data" else "handle_error"
    )
    
    workflow.add_conditional_edges(
        "analyze_data",
        lambda state: "generate_recommendation" if state.get("current_step") == "generate_recommendation" else "handle_error"
    )
    
    workflow.add_conditional_edges(
        "generate_recommendation",
        lambda state: "format_response" if state.get("current_step") == "format_response" else "handle_error"
    )
    
    # Add end edges
    workflow.add_edge("format_response", END)
    workflow.add_edge("handle_error", END)
    
    return workflow.compile()

# Convenience function to run the workflow
async def run_carrier_vetting(input_data: Dict[str, Any], tenant_id: str = None, user_id: str = None) -> Dict[str, Any]:
    """Run the carrier vetting workflow"""
    with tracer.start_as_current_span("carrier_vetting_workflow") as span:
        span.set_attribute("agent_id", "carrier_vetting")
        span.set_attribute("tenant_id", tenant_id or "unknown")
        span.set_attribute("user_id", user_id or "unknown")
        span.set_attribute("input_keys", list(input_data.keys()))
        
        # Initialize state - merge input_data with state
        initial_state = {
            "messages": [],
            "current_step": "start",
            "input_data": input_data,  # Keep the original input_data
            "dot_number": "",
            "fmcsa_data": {},
            "additional_data": {},
            "carrier_info": {},
            "safety_analysis": {},
            "insurance_analysis": {},
            "authority_analysis": {},
            "company_analysis": {},
            "recommendation": {},
            "formatted_response": {},
            "error": None,
            "execution_time_ms": 0,
            "tenant_id": tenant_id or "unknown",
            "user_id": user_id or "unknown",
            "_start_time": time.time(),
            **input_data  # Also add input_data at root level for flexibility
        }
        
        # Create and run graph
        graph = create_carrier_vetting_graph()
        result = await graph.ainvoke(initial_state)
        
        # Calculate execution time
        start_time = result.get("_start_time", time.time())
        execution_time = int((time.time() - start_time) * 1000)
        result["formatted_response"]["context"]["execution_time_ms"] = execution_time
        
        # Return formatted response
        return result["formatted_response"]
