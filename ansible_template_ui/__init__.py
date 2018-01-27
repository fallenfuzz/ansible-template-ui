#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2017-2018 Matt Martz
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

__version__ = '1.0.0'

import base64
import json
import os

import docker

from flask_lambda import FlaskLambda
from flask import request, jsonify


kwargs = {}
app_path = os.path.dirname(__file__)
kwargs.update({
    'static_url_path': '',
    'static_folder': os.path.join(
        os.path.abspath(app_path),
        'client'
    )
})

app = FlaskLambda(__name__, **kwargs)
@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/render', methods=['POST'])
def render_template():
    data = request.get_json()

    client = docker.from_env()
    try:
        container = client.containers.create(
            "ansible-template-ui",
            environment={
                'TEMPLATE': base64.b64encode(data['template']),
                'VARIABLES': base64.b64encode(data['variables'] or '{}')
            },
            mem_limit='96m',
        )
        container.start()
    except Exception as e:
        app.logger.exception('Failed to create and start container')
        return jsonify(**{'error': str(e)}), 400
    else:
        exit_status = container.wait()
        stdout = container.logs(stdout=True, stderr=False)
        stderr = container.logs(stdout=False, stderr=True)
        error = None
        try:
            response = json.loads(stdout)
        except ValueError:
            app.logger.exception('Could not parse JSON')
            error = stderr or 'Unknown Error'
        else:
            play = response['plays'][0]
            if exit_status != 0:
                error = play['tasks'][-1]['hosts']['localhost']['msg']
        if error:
            return jsonify(**{'error': error}), 400
    finally:
        try:
            container.remove(force=True)
        except NameError:
            pass

    content = play['tasks'][1]['hosts']['localhost']['content']
    return jsonify(**{'content': base64.b64decode(content)})