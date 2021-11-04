#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python3 OpenMRS/ICE test app:

Get patient information from OpenMRS, format and  send it through
ICE, add the evaluations and forecasts and re-save it as test_out.json.

"""

# Original information retained - modifications made by https://github.com/lrasmus
# in 2021.
__author__      = "HLN Consulting, LLC"
__copyright__   = "Copyright 2018, HLN Consulting, LLC"
__license__     = "BSD-2-Clause"

import requests
import pyiceclient
import json
import datetime

SESS = requests.Session()
# Get the actual values from https://openmrs.org/demo/
# (I know it's publicly available, but still felt weird committing credentials)
SESS.auth = ('user', 'pass')

# This assumes you're running ICE in a Docker container locally
ICE_SERVICE_ENDPOINT = 'http://localhost:32775/opencds-decision-support-service/api/resources/evaluate'
OPEN_MRS_ENDPOINT = 'https://openmrs-spa.org/openmrs/ws/fhir2/R4/'

# Given a patient identifier within OpenMRS (assumed to be the FHIR id, not the MRN)
# create a vMR structure that can be used by ICE.
# This is just a simple FHIR -> vMR translator
def get_vmr_patient(patient_id):
  openmrs_patient_uri = OPEN_MRS_ENDPOINT + 'Patient/' + patient_id
  headers={
    'Content-type':'application/json',
    'Accept':'application/json'
  }
  req = SESS.get(openmrs_patient_uri, headers=headers)
  rspstr = req.content.decode('utf-8')
  if req.status_code == 200:
    patient = json.loads(rspstr)
    return {
      "id": patient['identifier'][0]['value'],
      "firstName": patient['name'][0]['given'][0],
      "lastName": patient['name'][0]['family'],
      "gender": patient['gender'],
      "dob": patient['birthDate'].replace('-', ''),
      "evalDate": datetime.date.today().strftime('%Y%m%d'),
      "izs": [],
      "evaluations": [],
      "forecasts": []
    }
  else:
    print('Error: ' + str(req))
    return "Error"

# Given a patient identifier within OpenMRS (assumed to be the FHIR id, not the MRN)
# retrieve the immunization records for the patient and format them in the vMR format
# required by ICE.
# This returns the array of immunizations, not the entire vMR structure
def get_vmr_immunizations(patient_id):
  openmrs_patient_uri = OPEN_MRS_ENDPOINT + 'Immunization?patient=' + patient_id
  headers={
    'Content-type':'application/json',
    'Accept':'application/json'
  }
  req = SESS.get(openmrs_patient_uri, headers=headers)
  rspstr = req.content.decode('utf-8')
  if req.status_code != 200:
    print('Error: ' + str(req))
    return "Error"

  response = json.loads(rspstr)
  if response is None or response['total'] == 0:
    return []

  ice_immunizations = []
  for immunization in response['entry']:
    ice_immunizations.append([
      immunization['resource']['id'],
      datetime.datetime.strptime(immunization['resource']['occurrenceDateTime'], '%Y-%m-%dT%H:%M:%S%z').strftime('%Y%m%d'),
      # TODO: I didn't see these details in Immunization resources yet in OpenMRS
      "127: H1N1-09, injectable",
      "I"
    ])
  return ice_immunizations

# Hardcoding a test patient ID for now, since it's a POC
patient_id = '5b331b80-2681-4429-baee-9c39ba51c164'
patient = get_vmr_patient(patient_id)
immunizations = get_vmr_immunizations(patient_id)
patient['izs'] = immunizations

data = [patient]

# Leaving this here in case we ever want to go back to testing from provided sample data
#with open('tests/test.json') as json_data:
#    data = json.load(json_data)

request_vmr = pyiceclient.data2vmr(data)
response_vmr = pyiceclient.send_request(request_vmr, ICE_SERVICE_ENDPOINT)
(evaluation_list, forecast_list) = pyiceclient.process_vmr(response_vmr)
data[0]['evaluations'] = evaluation_list
data[0]['forecasts'] = forecast_list

with open('test_out.json', 'w') as outfile:
    json.dump(data, outfile, indent=4)

