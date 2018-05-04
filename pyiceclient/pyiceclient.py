#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python ICE client (pyiceclient):

A Python 3 module to convert ICE web client data structure to vMR,
send the vMR to ICE, and parse the output vMR. See test_pyiceclient.py
for a usage example.

See README for important caveats.

"""

__author__      = "HLN Consulting, LLC"
__copyright__   = "Copyright 2018, HLN Consulting, LLC"
__license__     = "BSD-2-Clause"

# standard imports
#

import requests
from collections import defaultdict
import uuid
import base64
import datetime
import re

# extra imports
#
import xmltodict # pip install xmltodict

# SERVER_ENDPOINT is the URL of the ICE evaluate web service - intended to be on the localhost
#
SERVER_ENDPOINT = "http://localhost/opencds-decision-support-service/evaluate"

# Keep a global session object in order to support HTTP KeepAlive with the ICE service
#
SESS = requests.Session()

"""ICE Web Client Data Structure
-----------------------------

The ICE Web Client is a web client for ICE located at:

https://cds.hln.com/iceweb/

This module is based on the ICE web client data structure, which looks
like this:

[
    {
        "id": "Patient ID Alphanumeric",
        "firstName": "First Name",
        "lastName": "Last Name",
        "gender": "M",
        "dob": "YYYYMMDD",
        "evalDate": "YYYYMMDD",
        "izs": [],
        "evaluations": [],
        "forecasts": []
    }
]

(Note that the ICE web client doesn't actually put evaluations and
forecasts in its data structure - but we use it here as part of this
module)

Where "izs" is a list of immunizations; each immunization is a list of:
 element 0: immunization id
 element 1: date of administration, YYYYMMDD
 element 2: code[: name] (e.g., "03: MMR") (name optional) (CVX for "I", ICD9/ICD10/SCT for "D")
 element 3: "I" (immunization) or "D" (disease) 

Where "evaluations" is a list of evaluations; each evaluation is a list of:
 element 0: immunization id
 element 1: date of administration, YYYYMMDD
 element 2: cvx_code (e.g., "03")
 element 3: vaccine group name (e.g., "Hep B Vaccine Group")
 element 4: validity ("true" or "false")
 element 5: dose number in series (e.g., "1", "2", "3", etc.)
 element 6  evaluation_code (e.g., "VALID"
 element 7: comma-separated evaluation_interpretation (e.g., "TOO_EARLY_LIVE_VIRUS,BELOW_MINIMUM_INTERVAL")
 element 8: evaluation_group_code (e.g., "100")

Where "forecasts" is a list of forecasts; each forecast is a list of:
 element 0: vaccine group name (e.g., "Hep B Vaccine Group")
 element 1: forecast concept (e.g., "FUTURE_RECOMMENDED")
 element 2: comma-separated forecast interpretation (e.g., "DUE_IN_FUTURE,HIGH_RISK")
 element 3: due date, YYYYMMDD
 element 4: forecast group code (e.g., "100")
 element 5: vaccine code recommended (CVX code, if any)
 element 6: earliest date, YYYYMMDD
 element 7: past due date, YYYYMMDD

"""

#
# Global variables for ICE Web data structure list indexes (see ICE data structure
# documentation above)
#

ICE_IZS_ID = 0
ICE_IZS_DATE = 1
ICE_IZS_CODE = 2
ICE_IZS_I_OR_D = 3

ICE_EVALS_ID = 0
ICE_EVALS_DATE_OF_ADMIN = 1
ICE_EVALS_VACCINE = 2
ICE_EVALS_GROUP = 3
ICE_EVALS_VALIDITY = 4
ICE_EVALS_DOSE_NUM = 5
ICE_EVALS_EVAL_CODE = 6
ICE_EVALS_EVAL_INTERP = 7
ICE_EVALS_GROUP_CODE = 8

ICE_FORECASTS_GROUP = 0
ICE_FORECASTS_CONCEPT = 1
ICE_FORECASTS_INTERP = 2
ICE_FORECASTS_DUE_DATE = 3
ICE_FORECASTS_GROUP_CODE = 4
ICE_FORECASTS_VAC_CODE = 5
ICE_FORECASTS_EARLIEST_DATE = 6
ICE_FORECASTS_PAST_DUE_DATE = 7

#
# XML templates for ICE web service call - substitutions are marked as %s
#

# POST_PAYLOAD: XML for SOAP call. substitutions: 
#  specifiedTime as YYYY-MM-DD
#  base64EncodedPayload as b64-ascii-encoded vMR
#
POST_PAYLOAD = '''<?xml version="1.0" encoding="utf-8"?>
<S:Envelope xmlns:S="http://www.w3.org/2003/05/soap-envelope">
  <S:Body>
    <ns2:evaluateAtSpecifiedTime xmlns:ns2="http://www.omg.org/spec/CDSS/201105/dss">
      <interactionId scopingEntityId="gov.nyc.health" interactionId="123456"/>
      <specifiedTime>%s</specifiedTime>
      <evaluationRequest clientLanguage="" clientTimeZoneOffset="">
        <kmEvaluationRequest>
          <kmId scopingEntityId="org.nyc.cir" businessId="ICE" version="1.0.0"/>
        </kmEvaluationRequest>
        <dataRequirementItemData>
          <driId itemId="cdsPayload">
            <containingEntityId scopingEntityId="gov.nyc.health" businessId="ICEData" version="1.0.0.0"/>
          </driId>
          <data>
            <informationModelSSId scopingEntityId="org.opencds.vmr" businessId="VMR" version="1.0"/>
            <base64EncodedPayload>%s</base64EncodedPayload>
          </data>
        </dataRequirementItemData>
      </evaluationRequest>
    </ns2:evaluateAtSpecifiedTime>
  </S:Body>
</S:Envelope>'''

# VMR_HEADER: vMR header up through substanceAdministrationEvents. substitutions:
#  UUID
#  DOB in YYYYMMDD
#  Gender as M, F, O (?)
#
VMR_HEADER = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ns3:cdsInput xmlns:ns2="org.opencds.vmr.v1_0.schema.vmr" xmlns:ns3="org.opencds.vmr.v1_0.schema.cdsinput">
  <templateId root="2.16.840.1.113883.3.795.11.1.1"/>
  <cdsContext>
    <cdsSystemUserPreferredLanguage code="en" codeSystem="2.16.840.1.113883.6.99" displayName="English"/>
  </cdsContext>
  <vmrInput>
    <templateId root="2.16.840.1.113883.3.795.11.1.1"/>
    <patient>
      <templateId root="2.16.840.1.113883.3.795.11.2.1.1"/>
      <id root="%s"/>
      <demographics>
      <birthTime value="%s"/>
      <gender code="%s" codeSystem="2.16.840.1.113883.5.1"/>
      </demographics>
      <clinicalStatements>
      <observationResults/>
      <substanceAdministrationEvents>
'''

# VMR_IZ: vMR substanceAdministrationEvent. substitutions:
#  UUID
#  UUID
#  CVX code
#  date_of_admin in YYYYMMDD
#  date_of_admin in YYYYMMDD
#
VMR_IZ = '''<substanceAdministrationEvent>
            <templateId root="2.16.840.1.113883.3.795.11.9.1.1"/>
            <id root="%s"/>
            <substanceAdministrationGeneralPurpose code="384810002" codeSystem="2.16.840.1.113883.6.5"/>
            <substance>
              <id root="%s"/>
              <substanceCode code="%s" codeSystem="2.16.840.1.113883.12.292"/>
            </substance>
            <administrationTimeInterval low="%s" high="%s"/>
          </substanceAdministrationEvent>
'''

# VMR_DISEASE: vMR immunity observationResult. substitutions:
#  UUID
#  code
#  code system (2.16.840.1.113883.6.103 for ICD9, 
#               2.16.840.1.113883.6.90 for ICD10, 
#               2.16.840.1.113883.6.96 for SNOMED CT)
#  date_of_observation in YYYYMMDD
#  date_of_observation in YYYYMMDD
#
VMR_DISEASE = '''<observationResult>
  <templateId root="2.16.840.1.113883.3.795.11.6.3.1"/>
  <id root="%s"/>
  <observationFocus code="%s" codeSystem="%s"/> 
  <observationEventTime low="%s" high="%s"/>
  <observationValue>
    <concept code="DISEASE_DOCUMENTED" codeSystem="2.16.840.1.113883.3.795.12.100.8"/>
  </observationValue>
  <interpretation code="IS_IMMUNE" codeSystem="2.16.840.1.113883.3.795.12.100.9"/>
</observationResult>
'''

# VMR_FOOTER: vMR footer closing out substanceAdministrationEvents and the vMR. No substitutions.
#
VMR_FOOTER = '''</substanceAdministrationEvents>
      </clinicalStatements>
    </patient>
  </vmrInput>
</ns3:cdsInput>
'''

# regular expressions
#
RE_YYYYMMDD = re.compile("([0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])")
RE_ICD9 = re.compile("([V\d]\d{2}(\.?\d{0,2})?|E\d{3}(\.?\d)?|\d{2}(\.?\d{0,2})?)")
RE_ICD10 = re.compile("([A-TV-Z][0-9][A-Z0-9](\.?[A-Z0-9]{0,4})?)")
RE_SCT = re.compile("[0-9]{6}[0-9]*")

# code system OIDs
#
ICD9_OID = "2.16.840.1.113883.6.103"
ICD10_OID = "2.16.840.1.113883.6.90"
SCT_OID = "2.16.840.1.113883.6.96"

#
# functions
#


def send_request(in_vmr, as_of_date):
    """Take a vMR string and send it to ICE with the supplied as_of_date
    (YYYY-MM-DD). Return the output vMR string.

    """

    b64_payload = base64.b64encode(bytes(in_vmr, 'utf-8')).decode('ascii')
    data = POST_PAYLOAD % (as_of_date, b64_payload)
    data = data.replace('\n', '').replace('\r', '').encode('utf-8')
    req = SESS.post(SERVER_ENDPOINT, data=data)
    rspstr = req.content.decode('utf-8')
    if req.status_code == 200:
        resp_dict = xmltodict.parse(rspstr)
        b64_response = resp_dict['soap:Envelope']['soap:Body']['ns2:evaluateAtSpecifiedTimeResponse']['evaluationResponse']['finalKMEvaluationResponse']['kmEvaluationResultData']['data']['base64EncodedPayload']
        decoded_response = base64.b64decode(b64_response)
        return decoded_response
    else:
        print('crap: ' + str(req))
        return "crap"


def process_vmr(in_vmr):
    """Take an output vMR string and parse it. Return a tuple consisting
    of an evaluation list and a recommendation list.

    """
    evaluation_list = []
    recommendation_list = []

    vmr_dict = xmltodict.parse(in_vmr, process_namespaces=True, force_list=('substanceAdministrationEvent', 'relatedClinicalStatement', 'substanceAdministrationProposal', 'interpretation'))

    # evaluations 
    #
    if 'substanceAdministrationEvents' in vmr_dict['org.opencds.vmr.v1_0.schema.cdsoutput:cdsOutput']['vmrOutput']['patient']['clinicalStatements']:
        for substanceAdministrationEvent in vmr_dict['org.opencds.vmr.v1_0.schema.cdsoutput:cdsOutput']['vmrOutput']['patient']['clinicalStatements']['substanceAdministrationEvents']['substanceAdministrationEvent']:
            immunization_id = substanceAdministrationEvent['id']['@root']
            cvx = substanceAdministrationEvent['substance']['substanceCode']['@code']
            date_of_admin = RE_YYYYMMDD.findall(substanceAdministrationEvent['administrationTimeInterval']['@high'])[0]

            if 'relatedClinicalStatement' in substanceAdministrationEvent:
                for relatedClinicalStatement in substanceAdministrationEvent['relatedClinicalStatement']:

                    for inside_substanceAdministrationEvent in relatedClinicalStatement['substanceAdministrationEvent']:
                        is_valid = inside_substanceAdministrationEvent['isValid']['@value']
                        dose_number = inside_substanceAdministrationEvent['doseNumber']['@value']
                        evaluation_interpretation = ''

                        for inside_relatedClinicalStatement in inside_substanceAdministrationEvent['relatedClinicalStatement']:
                            evaluation_code = inside_relatedClinicalStatement['observationResult']['observationValue']['concept']['@code']
                            evaluation_group = inside_relatedClinicalStatement['observationResult']['observationFocus']['@displayName']
                            evaluation_group_code = inside_relatedClinicalStatement['observationResult']['observationFocus']['@code']
                            if 'interpretation' in inside_relatedClinicalStatement['observationResult']:
                                for interpretation in inside_relatedClinicalStatement['observationResult']['interpretation']:
                                    if len(evaluation_interpretation) > 0:
                                        evaluation_interpretation += ","
                                    evaluation_interpretation += interpretation['@code']

                        evaluation_list.append([immunization_id, date_of_admin, cvx, evaluation_group, is_valid, dose_number, evaluation_code, evaluation_interpretation, evaluation_group_code])
            else:
                evaluation_list.append([immunization_id, date_of_admin, cvx, 'Unsupported', 'unsupported', '0', 'UNSUPPORTED', '', '0'])

    # forecasts
    #
    for substanceAdministrationProposal in vmr_dict['org.opencds.vmr.v1_0.schema.cdsoutput:cdsOutput']['vmrOutput']['patient']['clinicalStatements']['substanceAdministrationProposals']['substanceAdministrationProposal']:

        substance_code = ''
        if substanceAdministrationProposal['substance']['substanceCode']['@codeSystem'] == '2.16.840.1.113883.12.292':
            substance_code = substanceAdministrationProposal['substance']['substanceCode']['@code']

        for relatedClinicalStatement in substanceAdministrationProposal['relatedClinicalStatement']:
            vaccine_group = relatedClinicalStatement['observationResult']['observationFocus']['@displayName']
            vaccine_group_code = relatedClinicalStatement['observationResult']['observationFocus']['@code']
            forecast_concept = relatedClinicalStatement['observationResult']['observationValue']['concept']['@code']
            forecast_interpretation = ''
            if 'interpretation' in relatedClinicalStatement['observationResult']:
                for interpretation in relatedClinicalStatement['observationResult']['interpretation']:
                    if len(forecast_interpretation) > 0:
                        forecast_interpretation += ","
                    forecast_interpretation += interpretation['@code']
            rec_date = ''
            pastdue_date = ''
            earliest_date = ''
            if 'proposedAdministrationTimeInterval' in substanceAdministrationProposal:
                rec_date = RE_YYYYMMDD.findall(substanceAdministrationProposal['proposedAdministrationTimeInterval']['@low'])[0]
                if '@high' in substanceAdministrationProposal['proposedAdministrationTimeInterval']:
                    pastdue_date = RE_YYYYMMDD.findall(substanceAdministrationProposal['proposedAdministrationTimeInterval']['@high'])[0]
            if 'validAdministrationTimeInterval' in substanceAdministrationProposal:
                earliest_date = RE_YYYYMMDD.findall(substanceAdministrationProposal['validAdministrationTimeInterval']['@low'])[0]

        recommendation_list.append([vaccine_group, forecast_concept, forecast_interpretation, rec_date, vaccine_group_code, substance_code, earliest_date, pastdue_date])
    
    return (evaluation_list, recommendation_list)


def data2vmr(data):
    """Take an ICE web client-style data structure and transform it into a
    vMR. Assumes only one child (index 0) in the data
    structure. Return vMR.

    To keep the ICE web client-style data structure simple, we accept
    ICD10, ICD9, or SNOMED CT codes for disease/immunity and figure
    out ourselves what the coding system is based on regex pattern
    matching on the code itself.

    """

    vmr_body = VMR_HEADER % (str(uuid.uuid4()), data[0]['dob'], data[0]['gender'])
    observation_results = ""
    
    for iz in data[0]['izs']:
        code = iz[ICE_IZS_CODE].split(':')[0]
        date = iz[ICE_IZS_DATE]
        if len(code) > 0 and len(date) > 0:
            if iz[ICE_IZS_I_OR_D] == 'I':
                vmr_body += VMR_IZ % (iz[ICE_IZS_ID], str(uuid.uuid4()), code, date, date)
            if iz[ICE_IZS_I_OR_D] == 'D':
                if RE_SCT.match(code):
                    observation_results += VMR_DISEASE % (str(uuid.uuid4()), code, SCT_OID, date, date)
                elif RE_ICD10.match(code):
                    observation_results += VMR_DISEASE % (str(uuid.uuid4()), code, ICD10_OID, date, date)
                elif RE_ICD9.match(code):
                    observation_results += VMR_DISEASE % (str(uuid.uuid4()), code, ICD9_OID, date, date)
                else:
                    pass


    if len(observation_results) > 0:
        vmr_body = vmr_body.replace('<observationResults/>','<observationResults>' + observation_results + '</observationResults>')

    vmr_body += VMR_FOOTER
    return vmr_body
