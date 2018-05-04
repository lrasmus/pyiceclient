#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python3 ICE client demo/test app:

Take a test.json file saved by the ICE web client, send it through
ICE, add the evaluations and forecasts and re-save it as test_out.json.

"""

__author__      = "HLN Consulting, LLC"
__copyright__   = "Copyright 2018, HLN Consulting, LLC"
__license__     = "BSD-2-Clause"

import pyiceclient
import json
import datetime

with open('tests/test.json') as json_data:
    data = json.load(json_data)

request_vmr = pyiceclient.data2vmr(data)
response_vmr = pyiceclient.send_request(request_vmr, datetime.date.today().strftime('%Y-%m-%d'))
(evaluation_list, forecast_list) = pyiceclient.process_vmr(response_vmr)
data[0]['evaluations'] = evaluation_list
data[0]['forecasts'] = forecast_list

with open('test_out.json', 'w') as outfile:
    json.dump(data, outfile, indent=4)

