# OpenMRS / ICE - AMIA 2021 Connectathon Project

This was a brief exploration/proof-of-concept project conducted as part of the AMIA 2021 Annual Symposium workshop: "W07: Connectathon: Making Open-Source Global Health Systems Talk to Each Other".  This event was organized by the [AMIA Global Health Informatics Working Group](https://amia.org/community/working-groups/global-health-informatics), and sponsored in part by the [AMIA Open Source Working Group](https://amia.org/community/working-groups/open-source).

## Scope

The scope of this project was very minimal:

1. Try out immunization data available for testing in [OpenMRS](https://openmrs.org/)
2. See if we can retrieve immunization data from OpenMRS and connect it to the [Immunization Calculation Engine (ICE)](https://www.hln.com/services/open-source/ice/index.html)

## Setup

I grabbed a copy of the [ICE Docker container](https://hub.docker.com/r/hlnconsulting/ice) using the instructions provided.

```
docker pull hlnconsulting/ice:latest
docker run --log-opt max-size=100m --log-opt max-file=5 --rm -d -p 32775:8080 --name ice hlnconsulting/ice:latest
```

If you want to keep an eye on the ICE logs while you're testing, run:

```
docker logs -f ice
```

You will need to modify [tests/test_pyiceclient.py](tests/test_pyiceclient.py) with the OpenMRS credentials [found on the OpenMRS Demo website](https://openmrs.org/demo/).  Adjust the endpoints as well, as needed.

From here, just run:

```
python tests/test_pyiceclient.py
```


## AMIA 2021 Connectathon Notebook

This got ICE running locally for me with an active API at `http://localhost:32775/opencds-decision-support-service/api/resources/evaluate`.  I tested that it was working correctly by [running `curl-rest-tests`](https://github.com/cdsframework/ice/tree/master/curl-rest-tests).

Next I wanted to do something more with ICE.  This repository is a modified fork of [pyiceclient](https://github.com/cdsframework/pyiceclient).  Some of the envelope for the requests had changed, so [I made a few changes](https://github.com/lrasmus/pyiceclient/commit/29952c866f137aafaa1823ec16bd00314468d25e) until it worked.

From here I needed to take the data from OpenMRS (available via FHIR) and convert it to the [vMR format that ICE wants](https://github.com/cdsframework/pyiceclient#ice-web-client-data-structure).  This was relatively straightforward to do, thanks to great documentation!

Now it was time to get the Immunization data.  Here I ran into a few snags.  It was easy enough to get the Immunization records from OpenMRS, but the CVX code and vaccine details didn't seem to be populated.  It was around this point that I ran out of time so I just hardcoded `"127: H1N1-09, injectable"`.  This at least lets us prove data can be sent and returned.

Then I just needed to run the test app:

```
python tests/test_pyiceclient.py
```

It wrote results to `test_out.json`, and you can review in there the vaccine schedule.

### Thoughts and Next Steps

For me this was a great learning experience.  I got some hands-on time with OpenMRS and ICE.  Both systems are really well documented and were very easy to get set up and running.  That's to say, all of this work should be credited to those projects and developers - I did very little (outside of learning) thanks to them.

This shows that we can easily bridge from OpenMRS to ICE and get JSON results.  But we need to get this actually in OpenMRS.  I don't know what has been done already, so I didn't want to go too far ahead with what integration may be best for the community.

[ICE has a really nice UI](https://cds.hln.com/iceweb/), so it may be better to try and connect with that UI directly instead of recreating it using the JSON response.  But, both options seem possible.


Original README - Python ICE Client (pyiceclient)
===============================

A Python 3 module to convert ICE web client data structure to vMR,
send the vMR to ICE, and parse the output vMR. See test_pyiceclient.py
for a usage example.

The example program test_pyiceclient.py takes a test.json file saved
by the ICE web client, and then uses the pyiceclient module to send it
through ICE, adds the evaluations and forecasts, and re-saves it as
test_out.json.

LICENSE
=======

See license in LICENSE file.

ICE Software
============

This module requires ICE server software to be accessible via a URL
specified in the send_request call.

The ICE server software is open source software with an open source
license available at www.cdsframework.org > ICE > Documentation > Open
Source License.

New ICE releases include schedule updates/new vaccines, new features,
and bug fixes; release notes are available at www.cdsframework.org >
ICE > Release Notes; and the software is available for download at
www.cdsframework.org > ICE > Downloads. 

ICE Web Client Data Structure
=============================

The ICE Web Client is a web client for ICE located at:

https://cds.hln.com/iceweb/

This module is based on the ICE web client data structure, which looks
like this:

```
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
```

(Note that the ICE web client doesn't actually put evaluations and
forecasts in its data structure - but we use it here as part of this
module)

Where "izs" is a list of immunizations; each immunization is a list of:

* element 0: immunization id
* element 1: date of administration, YYYYMMDD
* element 2: code[: name] (e.g., "03: MMR") (name optional) (CVX for "I", ICD9/ICD10/SCT for "D")
* element 3: "I" (immunization) or "D" (disease) 

Where "evaluations" is a list of evaluations; each evaluation is a list of:

* element 0: immunization id
* element 1: date of administration, YYYYMMDD
* element 2: cvx_code (e.g., "03")
* element 3: vaccine group name (e.g., "Hep B Vaccine Group")
* element 4: validity ("true" or "false" or "unsupported")
* element 5: dose number in series (e.g., "1", "2", "3", etc., or "0" if unsupported)
* element 6  evaluation_code (e.g., "VALID")
* element 7: comma-separated evaluation_interpretation (e.g., "TOO_EARLY_LIVE_VIRUS,BELOW_MINIMUM_INTERVAL")
* element 8: evaluation_group_code (e.g., "100")

Where "forecasts" is a list of forecasts; each forecast is a list of:

* element 0: vaccine group name (e.g., "Hep B Vaccine Group")
* element 1: forecast concept (e.g., "FUTURE_RECOMMENDED")
* element 2: comma-separated forecast interpretation (e.g., "DUE_IN_FUTURE,HIGH_RISK")
* element 3: due date, YYYYMMDD
* element 4: forecast group code (e.g., "100")
* element 5: vaccine code recommended (CVX code, if any)
* element 6: earliest date, YYYYMMDD
* element 7: past due date, YYYYMMDD


The ICE Default Immunization Schedule
=====================================

The ICE Default Immunization schedule was developed by a group of
Subject Matter Experts, based on ACIP recommendations and informed by
CDC's Clinical Decision Support for Immunizations (CDSi) - but its
rules do differ in some ways from CDSi, and its output may not always
match what an individual clinician may expect. Users are advised to be
familiar with the rules and decisions documented at
www.cdsframework.org > ICE > Documentation > Default Immunization
Schedule, and, of course, to use their clinical judgement in
interpreting the recommendations.

Limitations
===========

* Does not perform error checking on input; for example, invalid CVX
  codes or invalid evidence of immunity codes will be passed to ICE
  as-is.

* Earliest date and Past Due date simply returns whatever ICE
  returns. Therefore, if the ICE server's
  **output_earliest_and_overdue_dates** setting in *ice.properties* is
  "N", the earliest date will always be empty and the past due date
  will always be equal to the due date. If the
  **output_earliest_and_overdue_dates** setting is "Y", then the
  earliest date and the past due date will be populated for supported
  vaccine groups (as of March 2018 they are Meningococcal ACWY, Polio,
  Rotavirus and Varicella) in cases where ICE calculates such dates,
  and will be empty otherwise.

* Immunizations that are unsupported by ICE will return a list item in the evaluations list as follows:

  * element 0: immunization id
  * element 1: date of administration, YYYYMMDD
  * element 2: cvx_code (e.g., "03")
  * element 3: vaccine group name ("Unsupported")
  * element 4: validity ("unsupported")
  * element 5: dose number in series ("0")
  * element 6  evaluation_code ("UNSUPPORTED")
  * element 7: comma-separated evaluation_interpretation ("")
  * element 8: evaluation_group_code ("0")


Installation
============

System:
-------

* Install a working Python 3.5+ environment with pip
* Install ICE on the localhost

Python:
-------

* pip install xmltodict
* pip install requests

This project:
-------------

* Download release and unzip to project directory, or git clone <project url>; cd into project directory
* Modify options in test_pyiceclient.py as needed
* Test:

```
   $ python test_pyiceclient.py
```
* Review output files

Install as module:
-----------------

```
python setup.py build
sudo python setup.py install
```
