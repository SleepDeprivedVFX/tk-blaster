# Copyright (c) 2017 Adam Benson
#
__author__ = 'Adam Benson'
__version__ = '1.0.7'

import sgtk
import threading
import json
import urllib, urllib2
import sys, os, platform, time
import logging

# by importing QT from sgtk rather than directly, we ensure that
# the code will be compatible with both PySide and PyQt.
from sgtk.platform.qt import QtCore, QtGui
from .ui.clock_in_dialog import Ui_Dialog
from datetime import datetime, timedelta
from functools import partial

sg_engine = sgtk.platform.engine
path_from_engine = sg_engine

# ----------------------------------------------------------------------------------------------------------------------
# Global Variables
# ----------------------------------------------------------------------------------------------------------------------

# Define system variables
osSystem = platform.system()

if osSystem == 'Windows':
    base = '//hal'
    env_user = 'USERNAME'
    computername = 'COMPUTERNAME'
else:
    base = '/Volumes'
    env_user = 'USER'
    computername = 'HOSTNAME'

# I need to learn how to use this logger info.  It currently doesn't work.
app_log = sgtk.platform.get_logger('T-Sheets TEST: engine: %s' % sg_engine)

# Get T-Sheets Authorization
auth_id = 3
auth_filters = [
    ['id', 'is', auth_id]
]
auth_fields = ['code']

user_params = {'per_page': '50', 'active': 'yes'}
jobs_params = {'active': 'yes'}

url = 'https://rest.tsheets.com/api/v1/'

# Connect Logging
logger = logging.getLogger('t_sheets_connect')
logger.debug('tsheets_clock_in_dialog activated!')


def show_dialog(app_instance):
    """
    Shows the main dialog window.
    """
    # in order to handle UIs seamlessly, each toolkit engine has methods for launching
    # different types of windows. By using these methods, your windows will be correctly
    # decorated and handled in a consistent fashion by the system. 
    
    # we pass the dialog class to this method and leave the actual construction
    # to be carried out by toolkit.
    app_instance.engine.show_dialog("T-Sheets Connect", app_instance, AppDialog)


class AppDialog(QtGui.QWidget):
    """
    Main application dialog window
    """
    
    def __init__(self, timesheet_id=None, jobcode_id=None):
        """
        Constructor
        """
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self)
        
        # now load in the UI that was created in the UI designer
        self.ui = Ui_Dialog() 
        self.ui.setupUi(self)
        
        # most of the useful accessors are available through the Application class instance
        # it is often handy to keep a reference to this. You can get it via the following method:
        self._app = sgtk.platform.current_bundle()

        # via the self._app handle we can for example access:
        # - The engine, via self._app.engine
        # - A Shotgun API instance, via self._app.shotgun
        # - A tk API instance, via self._app.tk 

        auth_id = 3
        auth_filters = [
            ['id', 'is', auth_id]
        ]
        auth_fields = ['code']

        engine = self._app.engine
        self.sg = engine.sgtk

        auth_data = self.sg.shotgun.find_one('CustomNonProjectEntity06', auth_filters, auth_fields)
        authorization = auth_data['code']

        self.headers = {
            'Authorization': 'Bearer %s' % authorization
        }

        offset = (time.timezone if (time.localtime().tm_isdst == 0) else time.altzone) / 3600
        self.timezone = '-%02d:00' % offset

        # lastly, set up our very basic UI
        # The following is wrong.  It is currently pulling from the Shotgun Context instead of the T-Sheets context
        # I still need the shotgun context in case someone is not clocked in.
        setup_user = self.confirm_user()
        context = self._app.context
        project_info = context.project
        projectname = project_info['name']
        #self.ui.project_name.setText(project_info['name'])
        setup_name = context.user['name']
        self.ui.employee_name_2.setText(setup_name)
        task = context.task['name']
        #self.ui.task.setText(task)
        shot_asset = context.entity['name']
        self.ui.no_btn_2.clicked.connect(self.no)
        self.ui.current_project.setText(projectname)
        self.ui.current_task_label.setText(task)
        self.ui.current_entity_label.setText(shot_asset)
        self.ui.yes_btn_2.clicked.connect(partial(self.clock_in_ts_timesheet, ctx=self.get_sg_current_context()))

    # ------------------------------------------------------------------------------------------------------------------
    # T-Sheets Web Connection IO
    # ------------------------------------------------------------------------------------------------------------------
    def _send_to_tsheets(self, page=None, data=None):
        if page:
            if data:
                try:
                    packed_data = json.dumps(data)
                    request = urllib2.Request('%s%s' % (url, page), headers=self.headers, data=packed_data)
                    request.add_header('Content-Type', 'application/json')
                    response = urllib2.urlopen(request)
                    response_data = json.loads(response.read())
                    return response_data
                except Exception, e:
                    logger.error('CLOCK_IN: Send to T-Sheets connection failed!  Error: %s' % e)
            else:
                logger.warning('_send_to_tsheets(data) not detected!')

                return False
        else:
            logger.warning('_send_to_tsheets(page) not detected!')
            return False

    def _return_from_tsheets(self, page=None, data=None):
        if page:
            try:
                if data:
                    data_list = urllib.urlencode(data)
                    Q = '?'
                else:
                    data_list = ''
                    Q = ''
                request = urllib2.Request('%s%s%s%s' % (url, page, Q, data_list), headers=self.headers)
                response = urllib2.urlopen(request)
                response_data = json.loads(response.read())
                return response_data
            except Exception, e:
                logger.error('CLOCK_IN: Return from T-Sheets Connection Failed!  Error: %s' % e)
        else:
            logger.warning('_return_from_tsheets(page) not detected.')
            return False

    def _edit_tsheets(self, page=None, data=None):
        if page:
            if data:
                try:
                    # This is the way I was originally trying to PUT to the REST page, but it always returns 500 Error
                    opener = urllib2.build_opener(urllib2.HTTPHandler)
                    packed_data = json.dumps(data)
                    request = urllib2.Request('%s%s' % (url, page), headers=self.headers, data=packed_data)
                    request.add_header('Content-Type', 'application/json')
                    request.get_method = lambda: 'PUT'
                    response = opener.open(request)
                    response_data = json.loads(response.read())
                    return response_data
                except Exception, e:
                    logger.error('CLOCK_IN: Edit T-Sheets Connection Failed! Error: %s' % e)
            else:
                logger.warning('_edit_thseets(data) not detected.')

                return False
        else:
            logger.warning('_edit_thseets(page) not detected.')
            return False

    def return_subs(self, job_id=None):
        # this returns all children of a parent job id.  It does not return sub-children.
        logger.debug('return_subs initialized with job_id: %s' % job_id)
        if job_id:
            logger.debug('job_id:%s' % job_id)
            subjobsparams = {
                'parent_ids': job_id,
                'active': 'yes'
            }
            subjoblist = urllib.urlencode(subjobsparams)
            subjob_request = urllib2.Request('%sjobcodes?%s' % (url, subjoblist), headers=self.headers)
            subjob_js = json.loads(urllib2.urlopen(subjob_request).read())
            logger.debug('Info returned from T-Sheets via return_subs: %s' % subjob_js)
            for sj_type, sj_result in subjob_js.items():
                logger.debug('Testing subjob_js objects...')
                logger.debug('sj_type: %s' % sj_type)
                logger.debug('sj_result: %s' % sj_result)
                if sj_type == 'results':
                    logger.debug('results found: %s' % sj_result['jobcodes'])
                    sj_jobs_data = sj_result['jobcodes']
                    logger.debug('return_subs returns data: %s' % sj_jobs_data)
                    return sj_jobs_data
            logger.warning('return_subs data not processed!')
            return False
        logger.warning('return_subs data not processed!')
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Shotgun and T-Sheets User Information
    # ------------------------------------------------------------------------------------------------------------------
    def confirm_user(self):
        current_user = os.environ[env_user]
        current_comp = os.environ[computername]
        confirmed_user = False
        get_current_user = self.get_sg_user(sg_login=current_user)
        get_current_computer = self.get_sg_user(sg_computer=current_comp)
        if get_current_computer == get_current_user:
            user_data = get_current_user.values()[0]
            user_email = user_data['email']
            user_name = user_data['name']
            get_ts_user = self.get_ts_current_user_status(email=user_email)
            if get_ts_user:
                ts_user = '%s %s' % (get_ts_user['name'][0], get_ts_user['name'][1])
                if user_name == ts_user:
                    confirmed_user = get_ts_user
                else:
                    logger.warning('The User could not be confirmed on this computer.')
            else:
                logger.warning('confirm_user() has no value for get_ts_user data from get_ts_current_user_status()')
        return confirmed_user

    def get_sg_sequence_from_shot_id(self, shot_id=None):
        seq = {}
        if shot_id:
            filters = [
                ['id', 'is', shot_id]
            ]
            fields = [
                'sg_sequence'
            ]
            find_seq = self.sg.shotgun.find_one('Shot', filters, fields)
            if find_seq:
                seq_id = find_seq['sg_sequence']['id']
                seq_name = find_seq['sg_sequence']['name']
                seq[seq_id] = seq_name
        return seq

    def get_sg_user(self, userid=None, name=None, email=None, sg_login=None, sg_computer=None):
        """
        Get a specific Shotgun User's details from any basic input.
        Only the first detected value will be searched.  If all 3 values are added, only the ID will be searched.
        :param userid: (int) Shotgun User ID number
        :param name:   (str) First and Last Name
        :param email:  (str) email@asc-vfx.com
        :return: user: (dict) Basic details
        """

        user = {}
        if userid or name or email or sg_login or sg_computer:
            filters = [
                ['sg_status_list', 'is', 'act']
            ]
            if userid:
                filters.append(['id', 'is', userid])
            elif name:
                filters.append(['name', 'is', name])
            elif email:
                filters.append(['email', 'is', email])
            elif sg_login:
                filters.append(['login', 'is', sg_login])
            elif sg_computer:
                filters.append(['sg_computer', 'is', sg_computer])
            fields = [
                'email',
                'name',
                'sg_computer',
                'login',
                'permission_rule_set',
                'projects',
                'groups'
            ]
            find_user = self.sg.shotgun.find_one('HumanUser', filters, fields)
            if find_user:
                user_id = find_user['id']
                sg_email = find_user['email']
                computer = find_user['sg_computer']
                sg_name = find_user['name']
                # Dictionary {'type': 'PermissionRuleSet', 'id': 8 'name': 'Artist'}
                permissions = find_user['permission_rule_set']
                # List of Dictionaries [{'type': 'Group', 'id': 7, 'name':'VFX'}]
                groups = find_user['groups']
                login = find_user['login']
                # List of Dictionaries [{'type': 'Project', 'id': 168, 'name': 'masterTemplate'}]
                projects = find_user['projects']

                user[user_id] = {'name': sg_name, 'email': sg_email, 'computer': computer, 'permissions': permissions,
                                 'groups': groups, 'login': login, 'project': projects}
        else:
            logger.warning('No data passed to get_sg_user()!  Nothing processed!')
        return user

    def get_ts_active_users(self):
        ts_users = {}
        user_params = {'per_page': '50', 'active': 'yes'}
        user_js = self._return_from_tsheets(page='users', data=user_params)
        if user_js:
            for l_type, result_data in user_js.items():
                if l_type == 'results':
                    user_data = result_data['users']
                    for user in user_data:
                        data = user_data[user]
                        first_name = data['first_name']
                        last_name = data['last_name']
                        email = data['email']
                        last_active = data['last_active']
                        active = data['active']
                        username = data['username']
                        user_id = data['id']
                        name = first_name, last_name
                        ts_users[email] = {'name': name, 'last_active': last_active, 'active': active,
                                           'username': username, 'email': email, 'id': user_id}
            return ts_users
        logger.warning('get_ts_active_users has no data!')
        return False

    def get_ts_current_user_status(self, email=None):
        data = {}
        username = email
        # Send the Username from a script that already loads the shotgun data.  This returns the T-Sheets status of a
        # single user.
        all_users = self.get_ts_active_users()
        if username in all_users.keys():
            data = all_users[username]
        else:
            logger.warning('get_ts_current_user_status could not find the current user status!')
        return data

    # ------------------------------------------------------------------------------------------------------------------
    # T-Sheets Timesheet Workers
    # ------------------------------------------------------------------------------------------------------------------
    def get_iso_timestamp(self):
        iso_date = datetime.date(datetime.now()).isoformat()
        iso_time = '%02d:%02d:%02d' % (datetime.now().hour, datetime.now().minute, datetime.now().second)
        iso_tz = self.timezone
        clock_out = iso_date + 'T' + iso_time + iso_tz
        return clock_out

    def get_ts_user_timesheet(self, email=None):
        timesheet = {}
        _start_date = datetime.date((datetime.today() - timedelta(days=2)))
        current_user = self.get_ts_current_user_status(email=email)
        username = current_user['username']
        name = (current_user['name'][0] + ' ' + current_user['name'][1])
        first_name = current_user['name'][0]
        last_name = current_user['name'][1]
        ts_email = current_user['email']
        user_id = current_user['id']
        tsheet_param = {'start_date': _start_date, 'user_ids': user_id, 'on_the_clock': 'yes'}
        tsheets_json = self._return_from_tsheets(page='timesheets', data=tsheet_param)
        for type, data in tsheets_json.items():
            if type == 'results':
                ts_data = data.values()
                try:
                    for card, info in ts_data[0].items():
                        if info['on_the_clock']:
                            timesheet[card] = {'name': name, 'username': username, 'user_id': user_id, 'timecard': info}
                except AttributeError:
                    # User Not clocked in
                    logger.warning('get_ts_user_timesheet(): Likely cause is the user is not clocked in.')
                    pass
        return timesheet

    def check_sg_assignment(self, ctx=None, prj_id=None, user=None, status='ip'):
        if ctx and prj_id and user:
            task_id = ctx['task_id']
            username = user['name'][0] + ' ' + user['name'][1]
            user_email = user['email']
            user_id = self.get_sg_user(email=user_email).keys()[0]
            person_found = False
            people_list = []
            filters = [
                ['id', 'is', task_id]
            ]
            fields = [
                'task_assignees',
                'sg_status_list'
            ]
            current_task = self.sg.shotgun.find_one('Task', filters, fields=fields)
            if current_task:
                assignees = current_task['task_assignees']
                current_status = current_task['sg_status_list']
                if current_status != status:
                    data = {'sg_status_list': status}
                    self.sg.shotgun.update('Task', task_id, data)
                if assignees:
                    for person in assignees:
                        people_list.append(person)
                        if person['name'] == username:
                            person_found = True
                            break
                if not person_found:
                    people_list.append({'type': 'HumanUser', 'id': user_id})
                    data = {
                        'task_assignees': people_list
                    }
                    self.sg.shotgun.update('Task', task_id, data)

    def clock_in_ts_timesheet(self, ctx=None):
        """
        Clock_in_ts_timesheet is going to be a little tricky.
        It will have to split out the context, and then find the jobcode_id based on the project, shot/asset & job task.
        The user_id, start time and other things will have to be collected as well.
        :param ctx:
        :return:
        """
        logger.info('Clock in timesheet initializing...')
        self._app.engine.show_busy("T-Sheets is adjusting your Timesheet...",
                                   "If the window closes, the process has usually succeeded.  You are still"
                                   " responsible for your own time sheet!  You can double check by picking T-Sheets"
                                   " connect from the Shotgun menu, or by logging into T-Sheets and checking there.")
        assigned = self.ui.assigned.isChecked()
        new_ts = {}
        confirmed_user = self.confirm_user()
        if confirmed_user:
            logger.debug('User confirmed')
            self.no()
            if ctx:
                logger.debug('ctx found: %s' % ctx)
                user_id = confirmed_user['id']
                user_name = confirmed_user['name']
                start = self.get_iso_timestamp()
                project_id = ctx.keys()[0]
                ctx_data = ctx[project_id]
                project = ctx_data['project']
                project_jobcode = None
                task = ctx_data['task']
                shot_or_asset = ctx_data['name']
                sequence = ctx_data['sequence']
                context = ctx_data['context']
                if context == 'Asset':
                    ts_folder = 'Assets'
                elif context == 'Shot':
                    ts_folder = 'Shots'
                if assigned:
                    logger.info('Checking task assignment...')
                    self.check_sg_assignment(ctx=ctx_data, prj_id=project_id, user=confirmed_user)
                ts_projects = self.get_ts_active_projects()
                logger.debug('ts_projects returns: %s' % ts_projects)
                logger.debug('Searching ts_projects....')
                for pid, proj in ts_projects.items():
                    if proj == project:
                        logger.debug('Project match found! %s' % project)
                        project_jobcode = pid
                        break
                if project_jobcode:
                    logger.debug('Project Jobcode found!  Getting sub project data...')
                    ts_proj_subs = self.return_subs(project_jobcode)
                    if ts_proj_subs:
                        logger.debug('Sub Projects found!  Implementing search for matching data & sub folders...')
                        for folder_id, folder_data in ts_proj_subs.items():
                            if folder_data['name'] == ts_folder:
                                logger.debug('Matching sub task folder found in T-Sheets.')
                                if folder_data['has_children']:
                                    logger.debug('Matching sub task has children...')
                                    assets_seqs = self.return_subs(folder_id)
                                    if assets_seqs:
                                        logger.debug('Child has children...')
                                        for ass_seq_id, ass_seq_data in assets_seqs.items():
                                            if ts_folder == 'Assets':
                                                logger.debug('Asset level found')
                                                if ass_seq_data['name'] == shot_or_asset:
                                                    logger.debug('Matching Asset name found.  Returning ID')
                                                    jobcode_id = ass_seq_id
                                                    break
                                            elif ts_folder == 'Shots':
                                                logger.debug('Shot level found.')
                                                if ass_seq_data['name'] == sequence:
                                                    if ass_seq_data['has_children']:
                                                        get_shots = self.return_subs(ass_seq_id)
                                                        for shot_id, shot_data in get_shots.items():
                                                            if shot_data['name'] == shot_or_asset:
                                                                jobcode_id = shot_id
                                                                break
                                break
                    data = {'ids': jobcode_id}
                    get_jobcode = self._return_from_tsheets(page='jobcodes', data=data)
                    parse_data = get_jobcode['supplemental_data']
                    jobcodes = parse_data['jobcodes']
                    results = get_jobcode['results']['jobcodes']
                    for parent_ids, info in jobcodes.items():
                        if info['name'] == project:
                            ts_project = {'project_id': parent_ids, 'project_name': project}
                        elif info['name'] == context:
                            ts_context = {'context_id': parent_ids, 'shot_or_asset_name': context}
                    get_task_data = self._return_from_tsheets(page='customfields')
                    tasks = get_task_data['results']['customfields']
                    task_id = 0
                    for t, d in tasks.items():
                        if d['name'] == 'Job Tasks':
                            task_id = t
                            break
                    sg_to_ts_translation = self.get_sg_translator(sg_task=task)
                    task_translation = sg_to_ts_translation['task']
                    new_ts_data = {
                        "data":
                            [
                                {
                                    "user_id": user_id,
                                    "type": "regular",
                                    "start": "%s" % self.get_iso_timestamp(),
                                    "end": "",
                                    "jobcode_id": "%s" % jobcode_id,
                                    "notes": "Automatic timesheet update through Shotgun",
                                    "customfields": {
                                        task_id: "%s" % task_translation
                                    }
                                }
                            ]
                    }
                    new_ts = self._send_to_tsheets(page='timesheets', data=new_ts_data)
                    if new_ts:
                        logger.info('New Timesheet created successfully!')
        self._app.engine.clear_busy()
        return new_ts

    def get_ts_project_from_sg(self, project_name=None):
        project_info = {}
        if project_name:
            ts_projects = self.get_ts_active_projects()
            for ts_id, proj_name in ts_projects.items():
                if proj_name == project_name:
                    project_info[ts_id] = proj_name
        return project_info

    def get_ts_active_projects(self):
        jobs_params = {'active': 'yes'}
        jobs_js = self._return_from_tsheets(page='jobcodes', data=jobs_params)
        ts_projects = {}
        for j_type, result_data in jobs_js.items():
            if j_type == 'results':
                jobs_data = result_data['jobcodes']
                for project in jobs_data:
                    data = jobs_data[project]
                    has_children = data['has_children']
                    if has_children:
                        project_name = data['name']
                        project_id = data['id']
                        ts_projects[project_id] = project_name
        return ts_projects

    def get_ts_jobcode(self, jobcode=None):
        # print 'Get Jobcode %s' % jobcode
        jobcode_data = {}
        if jobcode:
            data = {'ids': jobcode}
            get_jobcode = self._return_from_tsheets(page='jobcodes', data=data)
            for keys in get_jobcode:
                if keys == 'results':
                    job_data = get_jobcode[keys]['jobcodes']
                    for job_id, job_info in job_data.items():
                        jobid = job_id
                        job_name = job_info['name']
                        has_children = job_info['has_children']
                        parent_id = job_info['parent_id']
                        jobcode_data[jobid] = {'name': job_name, 'has_children': has_children,
                                               'parent_id': parent_id}
        return jobcode_data

    def no(self):
        self.close()

    def get_sg_translator(self, sg_task=None):
        """
        The T-Sheets Translator requires a special Shotgun page to be created.
        The fields in the database are as follows:
        Database Name:  code:                (str) A casual name of the database.
        sgtask:         sg_sgtask:          (str-unique) The shotgun task. Specifically, '.main' namespaces are removed.
        tstask:         sg_tstask:          (str) The T-Sheets name for a task
        ts_short_code:  sg_ts_short_code:   (str) The ironically long name for a 3 letter code.
        task_depts:     sg_task_grp:        (multi-entity) Returns the groups that are associated with tasks
        people_override:sg_people_override: (multi-entity) Returns individuals assigned to specific tasks

         :param:        sg_task:            (str) Shotgun task name from context
        :return:        translation:        (dict) {
                                                    task: sg_tstask
                                                    short: sg_ts_short_code
                                                    dept: sg_task_depts
                                                    people: sg_people_override
                                                    }
        """
        translation = {}
        if sg_task:
            task_name = sg_task.split('.')[0]

            task_name = task_name.lower()

            filters = [
                ['sg_sgtask', 'is', task_name]
            ]
            fields = [
                'sg_sgtask',
                'sg_tstask',
                'sg_ts_short_code',
                'sg_task_grp',
                'sg_people_override'
            ]
            translation_data = self.sg.shotgun.find_one('CustomNonProjectEntity07', filters, fields=fields)

            if translation_data:
                task = translation_data['sg_tstask']
                short = translation_data['sg_ts_short_code']
                group = translation_data['sg_task_grp']
                people = translation_data['sg_people_override']
                translation = {'task': task, 'short': short, 'group': group, 'people': people}
            else:
                translation = {'task': 'General', 'short': 'gnrl', 'group': None, 'people': None}
        return translation

    def get_sg_current_context(self):
        """
        import sgtk
        tk = sgtk
        engine = tk.platform.current_engine()
        sg = engine.sgtk
        ctx = engine.context
        taskName = str(ctx).split(',')[0]
        project = ctx.project['name']
        entity = ctx.entity['type']
        print project, entity, taskName
        print ctx

        masterTemplate Shot anim.main
        anim.main, Shot MST110_029_370_cmp

        :return:
        """
        context = {}
        tk = sgtk
        engine = tk.platform.current_engine()
        ctx = engine.context
        task_name = ctx.task['name']
        task_id = ctx.task['id']
        project = ctx.project['name']
        project_id = ctx.project['id']
        shot_id = ctx.entity['id']
        shot = ctx.entity['name']
        entity_type = ctx.entity['type']
        if entity_type == 'Shot':
            seq_data = self.get_sg_sequence_from_shot_id(shot_id)
            for keys, name in seq_data.items():
                seq = name
                seq_id = keys
        else:
            seq = None
            seq_id = None
        context[project_id] = {
            'task': task_name,
            'task_id': task_id,
            'context': entity_type,
            'name': shot,
            'shot_id': shot_id,
            'project': project,
            'sequence': seq,
            'seq_id': seq_id
        }
        return context
