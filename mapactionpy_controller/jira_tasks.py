# -*- coding: utf-8 -*-
import logging
import netrc
import os
from datetime import datetime

import pytz
from jira import JIRA

# import mapactionpy_controller.task_renderer as task_renderer

logger = logging.getLogger(__name__)


def _get_secrets_from_netrc():
    possible_netrc_locations = [
        os.path.join(os.environ.get('HOME'], None), '.netrc'),
        os.path.join(os.environ.get('USERPROFILE'], None), '.netrc'),
        os.environ.get('MAPCHEF_NETRC', None)
    ]

    secrets = None
    for netrc_path in possible_netrc_locations:
        try:
            secrets = netrc.netrc(netrc_path)
        except IOError:
            pass

    return secrets


class JiraClient():
    jira_con = None
    board_details = None

    def __init__(self):
        self._get_jira_board_details()
        secrets = _get_secrets_from_netrc()

        if not secrets:
            err_msg = 'Unable to locate or load suitable `.netrc` file for JIRA integration'
            logger.error(err_msg)
            raise ValueError(err_msg)

        try:
            username, account, apikey = secrets.authenticators(self.jira_hostname)
        except TypeError:
            err_msg = 'JIRA Connection. Unable to find details for machine "{}" `.netrc` file.'.format(
                self.jira_hostname)
            logger.error(err_msg)
            raise ValueError(err_msg)

        self.jira_con = JIRA(options={'server': account}, basic_auth=(username, apikey))

        # Check that the user is actually authenticated
        if not self.jira_con.myself()['emailAddress'] == username:
            err_msg = 'JIRA Connection. Unable to authenticate with JIRA. Please check details in `.netrc` file.'
            logger.error(err_msg)
            raise ValueError(err_msg)

        logger.debug('JIRA Connection. Details = {}'.format(self.jira_con.myself()))

    def _get_jira_board_details(self):
        # TODO read these in from a config file
        self.jira_hostname = 'mapaction.atlassian.net'
        self.project_key = 'PIPET'
        # The target column should be were the column where new issues are created
        self.target_column = '10110'
        self.common_task_fields = {
            'project': self.project_key,
            'issuetype': {'id': '10096'}
        }

    def __del__(self):
        if self.jira_con:
            self.jira_con.kill_session()

    def task_handler(self, fail_threshold, msg, task_referal=None, **kwargs):
        logger.debug('JiraClient.task_handler called with status="{}", and msg="{}"'.format(
            fail_threshold, msg))

        if not task_referal:
            logger.debug('JiraClient.task_handler; `None` value passed for task_referal parameter. Nothing to handle.')
            return

        unique_summary = task_referal.get_task_unique_summary()
        task_desc = task_referal.get_task_description()

        j_issue = self.search_issue_by_unique_summary(unique_summary)

        if j_issue:
            # Update existing card and maybe move it back into "Doing" column
            self.update_jira_issue(j_issue, task_desc, fail_threshold)
        else:
            if fail_threshold > logging.INFO:
                # Create a new task
                self.create_new_jira_issue(unique_summary, task_desc)

    def search_issue_by_unique_summary(self, search_summary):
        found_issues = self.jira_con.search_issues(
            'project={} AND summary ~ "{}"'.format(self.project_key, search_summary), maxResults=2)

        if found_issues:
            if len(found_issues) > 1:
                raise ValueError(
                    'More than one JIRA Issue found with the summary "{}". This suggests that additional'
                    ' issues have been raised manualy on the board "{}". Please ensure that there is exactly'
                    ' one issues with this summary, by deleting those which have not been created by the'
                    ' user "{}"'.format(
                        search_summary,
                        self.project_key,
                        self.jira_con.myself()['emailAddress']
                    )
                )
            else:
                return found_issues[0]
        else:
            return None

    def create_new_jira_issue(self, unique_summary, task_desc):
        flds = self.common_task_fields.copy()
        flds['summary'] = unique_summary
        flds['description'] = task_desc

        new_task = self.jira_con.create_issue(fields=flds)
        print(new_task)

    def update_jira_issue(self, j_issue, task_desc, fail_threshold):
        now_utc = pytz.utc.localize(datetime.now())
        time_stamp = now_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')

        if fail_threshold > logging.INFO:
            prev_desc = j_issue.fields.description
            if task_desc != prev_desc:
                j_issue.update(description=task_desc)

            if j_issue.fields.status.id == self.target_column:
                self.jira_con.add_comment(
                    j_issue.id,
                    'This Issue was still current when MapChef was run at {}'.format(time_stamp))

            else:
                self.jira_con.add_comment(
                    j_issue.id,
                    'This Issue was still current on MapChef run at {}.'
                    ' Moving the issue to the TODO column'.format(time_stamp))
                # do transition
                # self.jira_con

            if j_issue.fields.status.id == self.target_column:
                self.jira_con.add_comment(
                    j_issue.id,
                    'This Issue appeared to be resolved when MapChef was run at {}. Please manually'
                    ' check that the outputs are as expected and then close this Issue.'.format(
                        time_stamp))


# testing
if __name__ == "__main__":
    my = JiraClient()
    # my.create_task_from_template()
    my_issue = my.jira_con.issue('TMIT2-4')
    # my_issue.update(description=task_renderer.get_task_description())

    print(my_issue)
    my_desc = my_issue.fields.description

    my_desc = my_desc.encode('ascii', 'backslashreplace')
    # replace(u'\u201c', '"')
    # my_desc.replace(u'\u201d', '"')
    print(u'my_issue.field.description = {}'.format(my_desc))
    print(u'my_issue.field.summary = {}'.format(my_issue.fields.summary))
    # emd = my.jira_con.editmeta('TMIT2-8')
    # print(emd)
    # print(ja.jira_con.myself()['emailAddress'])
    # print(ja.jira_con.projects())
    # update_data_task()
    # create_data_task('my-layer','MA0123')
    # search_for_data_task()
