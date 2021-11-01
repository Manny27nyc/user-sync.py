# Copyright (c) 2016-2017 Adobe Inc.  All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import logging

from ..config.common import DictConfig, OptionsBuilder
from ..cache.sign import SignCache
from ..error import AssertionException
from sign_client.client import SignClient
from pathlib import Path


class SignConnector(object):

    def __init__(self, caller_options, org_name, test_mode, connection):
        """
        :type caller_options: dict
        """
        self.console_org = org_name
        self.name = 'sign_{}'.format(self.console_org)
        self.logger = logging.getLogger(self.name)
        self.test_mode = test_mode
        caller_config = DictConfig('sign_configuration', caller_options)
        sign_builder = OptionsBuilder(caller_config)
        sign_builder.require_string_value('host')
        sign_builder.require_string_value('admin_email')
        self.create_users = sign_builder.require_value('create_users', bool)
        self.deactivate_users = sign_builder.require_value('deactivate_users', bool)
        store_path = sign_builder.require_value('cache', dict).get('path')

        options = sign_builder.get_options()
        integration_key = caller_config.get_credential('integration_key', options['admin_email'])
        caller_config.report_unused_values(self.logger)

        if store_path is None:
            raise AssertionException(f"Cache path must be specified in '{org_name}' connector config")

        self.cache = SignCache(Path(store_path), org_name)

        self.sign_client = SignClient(connection,
                                      host=options['host'],
                                      integration_key=integration_key,
                                      admin_email=options['admin_email'],
                                      logger=self.logger)

    def sign_groups(self):
        if self.cache.should_refresh:
            self.refresh_all()
        return {g.groupName.lower(): g for g in self.cache.get_groups()}

    def create_group(self, new_group):
        if not self.test_mode:
            self.sign_client.create_group(new_group)

    def get_users(self):
        if self.cache.should_refresh:
            self.refresh_all()
        return {user.id: user for user in self.cache.get_users() if user.status == 'ACTIVE'}

    def get_user_groups(self):
        if self.cache.should_refresh:
            self.refresh_all()
        return dict(self.cache.get_user_groups())

    def update_users(self, update_data):
        if not self.test_mode:
            self.sign_client.update_users(update_data)

    def update_user_groups(self, update_data):
        if not self.test_mode:
            self.sign_client.update_user_groups(update_data)

    def get_group(self, assignment_group):
        return [g.groupId for g in self.sign_client.groups if g.groupName.lower() == assignment_group.lower()][0]

    def insert_user(self, insert_data):
        if not self.test_mode:
            self.sign_client.insert_user(insert_data)

    def deactivate_user(self, user_id):
        if not self.test_mode:
            self.sign_client.deactivate_user(user_id)
    
    def refresh_all(self):
        self.refresh_users()
        self.refresh_groups()
        self.refresh_user_groups()
        self.cache.should_refresh = False
        self.cache.update_next_refresh()
    
    def refresh_users(self):
        for user in self.sign_client.get_users().values():
            self.cache.cache_user(user)
    
    def refresh_groups(self):
        for group in self.sign_client.sign_groups():
            self.cache.cache_group(group)

    def refresh_user_groups(self):
        user_ids = [u.id for u in self.cache.get_users()]
        for user_id, user_groups in self.sign_client.get_user_groups(user_ids).items():
            for user_group in user_groups.groupInfoList:
                self.cache.cache_user_group(user_id, user_group)