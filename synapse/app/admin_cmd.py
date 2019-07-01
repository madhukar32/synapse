#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016 OpenMarket Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import sys

from twisted.internet import defer, reactor

import synapse
from synapse.app import _base
from synapse.config._base import ConfigError
from synapse.config.homeserver import HomeServerConfig
from synapse.config.logger import setup_logging
from synapse.metrics.background_process_metrics import run_as_background_process
from synapse.replication.slave.storage._base import BaseSlavedStore
from synapse.replication.slave.storage.account_data import SlavedAccountDataStore
from synapse.replication.slave.storage.appservice import SlavedApplicationServiceStore
from synapse.replication.slave.storage.client_ips import SlavedClientIpStore
from synapse.replication.slave.storage.deviceinbox import SlavedDeviceInboxStore
from synapse.replication.slave.storage.devices import SlavedDeviceStore
from synapse.replication.slave.storage.events import SlavedEventStore
from synapse.replication.slave.storage.filtering import SlavedFilteringStore
from synapse.replication.slave.storage.groups import SlavedGroupServerStore
from synapse.replication.slave.storage.presence import SlavedPresenceStore
from synapse.replication.slave.storage.push_rule import SlavedPushRuleStore
from synapse.replication.slave.storage.receipts import SlavedReceiptsStore
from synapse.replication.slave.storage.registration import SlavedRegistrationStore
from synapse.replication.slave.storage.room import RoomStore
from synapse.replication.tcp.client import ReplicationClientHandler
from synapse.server import HomeServer
from synapse.storage.engines import create_engine
from synapse.util.logcontext import LoggingContext
from synapse.util.versionstring import get_version_string

logger = logging.getLogger("synapse.app.admin_cmd")


class AdminCmdSlavedStore(
    SlavedReceiptsStore,
    SlavedAccountDataStore,
    SlavedApplicationServiceStore,
    SlavedRegistrationStore,
    SlavedFilteringStore,
    SlavedPresenceStore,
    SlavedGroupServerStore,
    SlavedDeviceInboxStore,
    SlavedDeviceStore,
    SlavedPushRuleStore,
    SlavedEventStore,
    SlavedClientIpStore,
    RoomStore,
    BaseSlavedStore,
):
    pass


class AdminCmdServer(HomeServer):
    DATASTORE_CLASS = AdminCmdSlavedStore

    def _listen_http(self, listener_config):
        pass

    def start_listening(self, listeners):
        pass

    def build_tcp_replication(self):
        return AdminCmdReplicationHandler(self)


class AdminCmdReplicationHandler(ReplicationClientHandler):
    @defer.inlineCallbacks
    def on_rdata(self, stream_name, token, rows):
        pass

    def get_streams_to_replicate(self):
        return {}


@defer.inlineCallbacks
def do_foo(hs):
    from synapse.handlers.admin import FileExfiltrationWriter

    user_id = "@test:localhost:8480"
    res = yield hs.get_handlers().admin_handler.exfiltrate_user_data(
        user_id, FileExfiltrationWriter(user_id)
    )
    print(res)
    reactor.stop()


def start(config_options):
    try:
        config = HomeServerConfig.load_config("Synapse admin cmd", config_options)
    except ConfigError as e:
        sys.stderr.write("\n" + str(e) + "\n")
        sys.exit(1)

    # Update the config with some basic overrides
    config.worker_daemonize = False
    config.worker_log_file = None
    config.worker_log_config = None
    config.worker_app = "synapse.app.admin_cmd"
    config.worker_listeners = []

    config.update_user_directory = False
    config.start_pushers = False
    config.send_federation = False

    setup_logging(config, use_worker_options=True)

    synapse.events.USE_FROZEN_DICTS = config.use_frozen_dicts

    database_engine = create_engine(config.database_config)

    ss = AdminCmdServer(
        config.server_name,
        db_config=config.database_config,
        config=config,
        version_string="Synapse/" + get_version_string(synapse),
        database_engine=database_engine,
    )

    ss.setup()
    reactor.callWhenRunning(_base.start, ss, [])

    reactor.callWhenRunning(run_as_background_process, "do_foo", do_foo, ss)

    _base.start_worker_reactor("synapse-admin-cmd", config)


if __name__ == "__main__":
    with LoggingContext("main"):
        start(sys.argv[1:])
