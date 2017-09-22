import json
from datetime import datetime
import requests


#===================================================================================================
# 
#===================================================================================================
jenkins_url = 'https://eden.esss.com.br/jenkins/'
JENKINS_USER = 'damiani'
JENKINS_TOKEN = '5b7216899dadaa64785f9fa3d7dcef5b'


def get_last_build_errors(job_name): 
    
    url = jenkins_url + 'job/' + job_name + '/lastBuild/testReport/api/json?pretty=true&tree=suites[cases[className,name,status,errorStackTrace]]'
    r = requests.get(url, auth=(JENKINS_USER, JENKINS_TOKEN))
    if r.status_code != 200:
        return []

    try:
        result = json.loads(r.text)
    except:
        return []
    
    try:
        cases = result['suites'][0]['cases']
    except:
        print('Failed to get cases')
        return []
    
    
    errors = []
    for case in cases:
        if case['status'] == 'FAILED':
            errors.append(case)
    
    return errors


def format_build_info(last_build):
    for key, _value in list(last_build.items()):
        if key == 'timestamp':
            last_build['timestamp'] = datetime.fromtimestamp(last_build['timestamp'] / 1000)
            last_build['took'] = (datetime.now() - last_build['timestamp'])
        elif key == 'duration':
            last_build['duration'] = last_build['duration'] / 1000.0 / 60.0 # minutes
            
        if key == 'actions':
            for actions in _value:
                if 'causes' in actions:
                    for cause in actions['causes']:
                        if 'userId' in cause:
                            last_build['userId'] = cause['userId']
                            last_build['userName'] = cause['userName']
            del last_build['actions']
    
    return last_build


def get_job_last_build(job_name):
    url = jenkins_url + 'job/'  + job_name + '/lastBuild/api/json?pretty=true&tree=building,number,duration,builtOn,timestamp,result,estimatedDuration,actions[causes[*]]'
    r = requests.get(url, auth=(JENKINS_USER, JENKINS_TOKEN))
    if r.status_code != 200:
        print('Failed to get building jobs')
        return {}

    result = json.loads(r.text)
    return format_build_info(result)


def get_building_jobs():
    url = jenkins_url + 'api/json?pretty=true&tree=jobs[fullName,lastBuild[building,number,duration,builtOn,timestamp,result,estimatedDuration,actions[causes[*]]]]'
    r = requests.get(url, auth=(JENKINS_USER, JENKINS_TOKEN))

    result = json.loads(r.text)
    jobs = result['jobs']
    
    building_jobs = {}
    for job in jobs:
        if job['lastBuild'] is not None and job['lastBuild']['building']:
            job_build = format_build_info(job['lastBuild'])
#             job_build['fullName'] = job['fullName']
            building_jobs[job['fullName']] = job_build
            
    return building_jobs
