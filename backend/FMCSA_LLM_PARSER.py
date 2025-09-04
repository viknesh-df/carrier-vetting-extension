# FMCSA_LLM_PARSER.py

import json
import os
import requests
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def parse_fmcsa_with_llm(raw_data: Dict[str, Any]) -> str:
    """
    Parse FMCSA API response JSON into a structured summary using Groq LLM.
    Returns a JSON string.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment variables")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = """
    You are a compliance assistant that converts raw FMCSA carrier data into a structured JSON summary for both detailed reports and a simplified card view.

        Rules:
        - Always return valid JSON only, no extra text or explanation.
        - Do not invent fields that are not in the input data.
        - Normalize safety scores to 0-100 if available, otherwise use raw score.
        - For status, use "APPROVED", "REJECTED", or "REVIEW NEEDED".
        - Issues should be short human-readable risk factors.
        - Reviews should be positives written in plain English.

        The JSON must have these sections:

        {
        "carrier_summary": {
            "name": "...",
            "dot_number": "...",
            "location": "...",
            "operation": "...",
            "drivers": ...,
            "power_units": ...
        },
        "safety_overview": {
            "safety_rating": "...",
            "driver_oos_rate": "...",
            "vehicle_oos_rate": "...",
            "crashes": {
            "total": ...,
            "fatal": ...,
            "injury": ...,
            "towaway": ...
            }
        },
        "insurance_compliance": {
            "compliant": true/false,
            "details": [...]
        },
        "authority_status": {
            "active": true/false,
            "authority_types": [...],
            "score": ...
        },
        "recommendation": {
            "risk_level": "...",
            "decision": "APPROVED/REJECTED/REVIEW NEEDED",
            "confidence": "...",
            "positives": [...],
            "concerns": [...]
        },
        "scores": {
            "safety": ...,
            "insurance": ...,
            "authority": ...,
            "company": ...,
            "overall": ...
        },
        "card": {
            "status": "approved/rejected/review needed",
            "status_color": "green/red/orange",
            "safety_score": ...,
            "issues": [...],
            "reviews": [...]
        }
        }

        Make sure the all the above sections and fields are present in the output JSON.
        Do not give any extra sections other than mentioned above.

        Now convert the following FMCSA carrier data into this format:

    """

    user_prompt = f"""
    Convert the following FMCSA carrier data into the structured JSON format:

    {json.dumps(raw_data, indent=2)}

    Give only the JSON output, no explanations , extra symbols , or text.
    Ensure the JSON is valid and properly formatted. dont give ```
    """

    payload = {
        "model": "llama-3.3-70b-versatile",  # adjust if needed
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(f"Groq API error {response.status_code}: {response.text}")

    llm_output = response.json()["choices"][0]["message"]["content"].strip()

    # Try to validate JSON
    try:
        parsed = json.loads(llm_output)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        # If invalid JSON, just return raw LLM output
        return llm_output


raw_fmcsa_data = {'dot': '125550', 'source': 'fmcsa_api', 'retrieval_date': '2025-09-03T13:24:24.953+0000', 'carrier_info': {'legal_name': 'ATLAS VAN LINES INC', 'dba_name': None, 'dot_number': 125550, 'ein': 222543019, 'address': {'street': '1212 ST GEORGE ROAD', 'city': 'EVANSVILLE', 'state': 'IN', 'zipcode': '47711', 'country': 'US'}}, 'analysis': {'company_profile': {'total_drivers': 2417, 'total_power_units': 3243, 'company_score': 100}, 'safety_metrics': {'driver_oos_rate': 4.329524954900782, 'driver_oos_national_avg': 5.51, 'driver_safety_score': 60.7, 'vehicle_oos_rate': 26.27986348122867, 'vehicle_oos_national_avg': 20.72, 'vehicle_safety_score': 36.6, 'hazmat_oos_rate': 0.0, 'hazmat_oos_national_avg': 4.5, 'hazmat_safety_score': 100.0, 'total_crashes': 59, 'fatal_crashes': 0, 'injury_crashes': 20, 'towaway_crashes': 39, 'safety_rating': 'S', 'safety_rating_date': '2024-11-13', 'overall_safety_score': 65.8}, 'insurance_compliance': {'bipd_required': False, 'bipd_required_amount': 750.0, 'bipd_on_file': 1000.0, 'bipd_compliant': True, 'bond_required': True, 'bond_on_file': 75.0, 'bond_compliant': True, 'cargo_required': False, 'cargo_on_file': 5.0, 'cargo_compliant': True, 'fully_compliant': True, 'insurance_score': 300.0}, 'authority_status': {'authority_status': 'Unknown', 'authority_active': False, 'authority_score': 0}}, 'recommendation': {'overall_score': 116.5, 'risk_level': 'LOW', 'recommendation': 'APPROVED', 'confidence': 'HIGH', 'concerns': ['Low safety score', 'Inactive authority status'], 'positives': ['Fully compliant with insurance requirements', 'Complete company profile'], 'score_breakdown': {'safety': 65.8, 'insurance': 300.0, 'authority': 0, 'company': 100}}, 'evidence': {'raw_data': {'content': {'_links': {'basics': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/basics'}, 'cargo carried': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/cargo-carried'}, 'operation classification': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/operation-classification'}, 'docket numbers': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/docket-numbers'}, 'carrier active-For-hire authority': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/authority'}, 'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550'}}, 'carrier': {'allowedToOperate': 'Y', 'bipdInsuranceOnFile': '1000', 'bipdInsuranceRequired': 'u', 'bipdRequiredAmount': '750', 'bondInsuranceOnFile': '75', 'bondInsuranceRequired': 'Y', 'brokerAuthorityStatus': 'A', 'cargoInsuranceOnFile': '5', 'cargoInsuranceRequired': 'u', 'carrierOperation': {'carrierOperationCode': 'A', 'carrierOperationDesc': 'Interstate'}, 'censusTypeId': {'censusType': 'C', 'censusTypeDesc': 'CARRIER', 'censusTypeId': 1}, 'commonAuthorityStatus': 'A', 'contractAuthorityStatus': 'A', 'crashTotal': 59, 'dbaName': None, 'dotNumber': 125550, 'driverInsp': 1663, 'driverOosInsp': 72, 'driverOosRate': 4.329524954900782, 'driverOosRateNationalAverage': '5.51', 'ein': 222543019, 'fatalCrash': 0, 'hazmatInsp': 0, 'hazmatOosInsp': 0, 'hazmatOosRate': 0, 'hazmatOosRateNationalAverage': '4.5', 'injCrash': 20, 'isPassengerCarrier': 'N', 'issScore': None, 'legalName': 'ATLAS VAN LINES INC', 'mcs150Outdated': 'N', 'oosDate': None, 'oosRateNationalAverageYear': '2009-2010', 'phyCity': 'EVANSVILLE', 'phyCountry': 'US', 'phyState': 'IN', 'phyStreet': '1212 ST GEORGE ROAD', 'phyZipcode': '47711', 'reviewDate': '2024-11-08', 'reviewType': 'C', 'safetyRating': 'S', 'safetyRatingDate': '2024-11-13', 'safetyReviewDate': '2024-11-08', 'safetyReviewType': 'C', 'snapshotDate': None, 'statusCode': 'A', 'totalDrivers': 2417, 'totalPowerUnits': 3243, 'towawayCrash': 39, 'vehicleInsp': 879, 'vehicleOosInsp': 231, 'vehicleOosRate': 26.27986348122867, 'vehicleOosRateNationalAverage': '20.72'}}, 'retrievalDate': '2025-09-03T13:24:24.953+0000'}, 'additional_endpoints': {'basics': {'content': [{'basic': {'basicsPercentile': 'Not Public', 'basicsRunDate': '2017-01-27T05:00:00.000+0000', 'basicsType': {'basicsCode': 'Unsafe Driving', 'basicsCodeMcmis': None, 'basicsId': 11, 'basicsLongDesc': None, 'basicsShortDesc': 'Unsafe Driving'}, 'basicsViolationThreshold': '65', 'exceededFMCSAInterventionThreshold': '-1', 'id': {'basicsId': 11, 'dotNumber': 125550}, 'measureValue': '1.16', 'onRoadPerformanceThresholdViolationIndicator': 'Not Public', 'seriousViolationFromInvestigationPast12MonthIndicator': 'N', 'totalInspectionWithViolation': 337, 'totalViolation': 354}, 'dotNumber': None, '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/basics/11'}}}, {'basic': {'basicsPercentile': 'Not Public', 'basicsRunDate': '2017-01-27T05:00:00.000+0000', 'basicsType': {'basicsCode': 'HOS Compliance', 'basicsCodeMcmis': None, 'basicsId': 12, 'basicsLongDesc': None, 'basicsShortDesc': 'Hours-of-Service Compliance'}, 'basicsViolationThreshold': '65', 'exceededFMCSAInterventionThreshold': '-1', 'id': {'basicsId': 12, 'dotNumber': 125550}, 'measureValue': '0.76', 'onRoadPerformanceThresholdViolationIndicator': 'Not Public', 'seriousViolationFromInvestigationPast12MonthIndicator': 'N', 'totalInspectionWithViolation': 399, 'totalViolation': 489}, 'dotNumber': None, '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/basics/12'}}}, {'basic': {'basicsPercentile': 'Not Public', 'basicsRunDate': '2017-01-27T05:00:00.000+0000', 'basicsType': {'basicsCode': 'Driver Fitness', 'basicsCodeMcmis': None, 'basicsId': 13, 'basicsLongDesc': None, 'basicsShortDesc': 'Driver Fitness'}, 'basicsViolationThreshold': '80', 'exceededFMCSAInterventionThreshold': '-1', 'id': {'basicsId': 13, 'dotNumber': 125550}, 'measureValue': '0.1', 'onRoadPerformanceThresholdViolationIndicator': 'Not Public', 'seriousViolationFromInvestigationPast12MonthIndicator': 'Y', 'totalInspectionWithViolation': 57, 'totalViolation': 60}, 'dotNumber': None, '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/basics/13'}}}, {'basic': {'basicsPercentile': 'Not Public', 'basicsRunDate': '2017-01-27T05:00:00.000+0000', 'basicsType': {'basicsCode': 'Drugs/Alcohol', 'basicsCodeMcmis': None, 'basicsId': 14, 'basicsLongDesc': None, 'basicsShortDesc': 'Controlled Substances/&#8203;Alcohol'}, 'basicsViolationThreshold': '80', 'exceededFMCSAInterventionThreshold': '-1', 'id': {'basicsId': 14, 'dotNumber': 125550}, 'measureValue': '0.01', 'onRoadPerformanceThresholdViolationIndicator': 'Not Public', 'seriousViolationFromInvestigationPast12MonthIndicator': 'N', 'totalInspectionWithViolation': 8, 'totalViolation': 10}, 'dotNumber': None, '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/basics/14'}}}, {'basic': {'basicsPercentile': 'Not Public', 'basicsRunDate': '2017-01-27T05:00:00.000+0000', 'basicsType': {'basicsCode': 'Vehicle Maint.', 'basicsCodeMcmis': None, 'basicsId': 15, 'basicsLongDesc': None, 'basicsShortDesc': 'Vehicle Maintenance'}, 'basicsViolationThreshold': '80', 'exceededFMCSAInterventionThreshold': '-1', 'id': {'basicsId': 15, 'dotNumber': 125550}, 'measureValue': '3.75', 'onRoadPerformanceThresholdViolationIndicator': 'Not Public', 'seriousViolationFromInvestigationPast12MonthIndicator': 'Y', 'totalInspectionWithViolation': 888, 'totalViolation': 1783}, 'dotNumber': None, '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/basics/15'}}}], 'retrievalDate': '2025-09-03T13:24:26.497+0000'}, 'cargo_carried': {'content': [{'cargoClassDesc': 'General Freight', 'id': {'cargoClassId': 1, 'dotNumber': 125550}}, {'cargoClassDesc': 'Household Goods', 'id': {'cargoClassId': 2, 'dotNumber': 125550}}, {'cargoClassDesc': 'Motor Vehicles', 'id': {'cargoClassId': 4, 'dotNumber': 125550}}], 'retrievalDate': '2025-09-03T13:24:27.884+0000', '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/cargo-carried'}}}, 'operation_classification': {'content': [{'id': {'dotNumber': 125550, 'operationClassId': 1}, 'operationClassDesc': 'Authorized For Hire'}, {'id': {'dotNumber': 125550, 'operationClassId': 12}, 'operationClassDesc': 'Other'}], 'retrievalDate': '2025-09-03T13:24:29.026+0000', '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/operation-classification'}}}, 'docket_numbers': {'content': [{'docketNumber': 79658, 'docketNumberId': 30990, 'dotNumber': 125550, 'prefix': 'MC'}, {'docketNumber': 130921, 'docketNumberId': 616681, 'dotNumber': 125550, 'prefix': 'MC'}], 'retrievalDate': '2025-09-03T13:24:30.382+0000', '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/mc-numbers'}}}, 'authority': {'content': [{'carrierAuthority': {'applicantID': 7752, 'authority': 'N', 'authorizedForBroker': 'Y', 'authorizedForHouseholdGoods': 'N', 'authorizedForPassenger': 'N', 'authorizedForProperty': 'N', 'brokerAuthorityStatus': 'A', 'commonAuthorityStatus': 'N', 'contractAuthorityStatus': 'N', 'docketNumber': 130921, 'dotNumber': 125550, 'prefix': 'MC'}, '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/authority/7752'}}}, {'carrierAuthority': {'applicantID': 3614, 'authority': 'N', 'authorizedForBroker': 'Y', 'authorizedForHouseholdGoods': 'Y', 'authorizedForPassenger': 'N', 'authorizedForProperty': 'Y', 'brokerAuthorityStatus': 'A', 'commonAuthorityStatus': 'A', 'contractAuthorityStatus': 'A', 'docketNumber': 79658, 'dotNumber': 125550, 'prefix': 'MC'}, '_links': {'self': {'href': 'https://mobile.fmcsa.dot.gov/qc/services/carriers/125550/authority/3614'}}}], 'retrievalDate': '2025-09-03T13:24:32.666+0000'}}}, 'context': {'tenant': 'string', 'user': 'string', 'execution_time_ms': 0, 'timestamp': '2025-09-03T18:54:32.400656'}}


structured_output = parse_fmcsa_with_llm(raw_fmcsa_data)
print(structured_output)