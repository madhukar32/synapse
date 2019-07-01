# -*- coding: utf-8 -*-
# Copyright 2019 The Matrix.org Foundation C.I.C.
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

import synapse.api.errors
import synapse.handlers.admin
import synapse.rest.admin
import synapse.storage
from synapse.rest.client.v1 import login, room
from synapse.api.constants import EventTypes

from collections import Counter

from tests import unittest

from mock import Mock


class ExfiltrateData(unittest.HomeserverTestCase):
    servlets = [
        synapse.rest.admin.register_servlets_for_client_rest_resource,
        login.register_servlets,
        room.register_servlets,
    ]

    def prepare(self, reactor, clock, hs):
        self.admin_handler = hs.get_handlers().admin_handler

        self.user1 = self.register_user("user1", "password")
        self.token1 = self.login("user1", "password")

        self.user2 = self.register_user("user2", "password")
        self.token2 = self.login("user2", "password")

    def test_single_public_joined_room(self):
        room_id = self.helper.create_room_as(
            self.user1, tok=self.token1, is_public=True
        )
        self.helper.send(room_id, body="Hello!", tok=self.token1)
        self.helper.join(room_id, self.user2, tok=self.token2)
        self.helper.send(room_id, body="Hello again!", tok=self.token1)

        writer = Mock()

        self.get_success(self.admin_handler.exfiltrate_user_data(self.user2, writer))

        writer.write_events.assert_called()
        writer.write_state.assert_not_called()

        written_events = []
        for (called_room_id, events), _ in writer.write_events.call_args_list:
            self.assertEqual(called_room_id, room_id)
            written_events.extend(events)

        states = Counter(
            (event.type, getattr(event, "state_key", None)) for event in written_events
        )
        self.assertEqual(states[(EventTypes.Message, None)], 2)
        self.assertEqual(states[(EventTypes.Member, self.user1)], 1)
        self.assertEqual(states[(EventTypes.Member, self.user2)], 1)

    def test_single_private_joined_room(self):
        room_id = self.helper.create_room_as(self.user1, tok=self.token1)
        self.helper.send_state(
            room_id,
            EventTypes.RoomHistoryVisibility,
            body={"history_visibility": "joined"},
            tok=self.token1,
        )
        self.helper.send(room_id, body="Hello!", tok=self.token1)
        self.helper.join(room_id, self.user2, tok=self.token2)
        self.helper.send(room_id, body="Hello again!", tok=self.token1)

        writer = Mock()

        self.get_success(self.admin_handler.exfiltrate_user_data(self.user2, writer))

        writer.write_events.assert_called()
        writer.write_state.assert_called_once()

        written_events = []
        for (called_room_id, events), _ in writer.write_events.call_args_list:
            self.assertEqual(called_room_id, room_id)
            written_events.extend(events)

        states = Counter(
            (event.type, getattr(event, "state_key", None)) for event in written_events
        )
        self.assertEqual(states[(EventTypes.Message, None)], 1)
        self.assertEqual(states[(EventTypes.Member, self.user1)], 1)
        self.assertEqual(states[(EventTypes.Member, self.user2)], 1)

    def test_single_left_room(self):
        room_id = self.helper.create_room_as(self.user1, tok=self.token1)
        self.helper.send(room_id, body="Hello!", tok=self.token1)
        self.helper.join(room_id, self.user2, tok=self.token2)
        self.helper.send(room_id, body="Hello again!", tok=self.token1)
        self.helper.leave(room_id, self.user2, tok=self.token2)
        self.helper.send(room_id, body="Helloooooo!", tok=self.token1)

        writer = Mock()

        self.get_success(self.admin_handler.exfiltrate_user_data(self.user2, writer))

        writer.write_events.assert_called()
        writer.write_state.assert_not_called()

        written_events = []
        for (called_room_id, events), _ in writer.write_events.call_args_list:
            self.assertEqual(called_room_id, room_id)
            written_events.extend(events)

        states = Counter(
            (event.type, getattr(event, "state_key", None)) for event in written_events
        )
        self.assertEqual(states[(EventTypes.Message, None)], 2)
        self.assertEqual(states[(EventTypes.Member, self.user1)], 1)
        self.assertEqual(states[(EventTypes.Member, self.user2)], 2)

    def test_single_left_rejoined_private_room(self):
        room_id = self.helper.create_room_as(self.user1, tok=self.token1)
        self.helper.send_state(
            room_id,
            EventTypes.RoomHistoryVisibility,
            body={"history_visibility": "joined"},
            tok=self.token1,
        )
        self.helper.send(room_id, body="Hello!", tok=self.token1)
        self.helper.join(room_id, self.user2, tok=self.token2)
        self.helper.send(room_id, body="Hello again!", tok=self.token1)
        self.helper.leave(room_id, self.user2, tok=self.token2)
        self.helper.send(room_id, body="Helloooooo!", tok=self.token1)
        self.helper.join(room_id, self.user2, tok=self.token2)
        self.helper.send(room_id, body="Helloooooo!!", tok=self.token1)

        writer = Mock()

        self.get_success(self.admin_handler.exfiltrate_user_data(self.user2, writer))

        writer.write_events.assert_called_once()
        self.assertEqual(writer.write_state.call_count, 2)

        written_events = []
        for (called_room_id, events), _ in writer.write_events.call_args_list:
            self.assertEqual(called_room_id, room_id)
            written_events.extend(events)

        states = Counter(
            (event.type, getattr(event, "state_key", None)) for event in written_events
        )
        self.assertEqual(states[(EventTypes.Message, None)], 2)
        self.assertEqual(states[(EventTypes.Member, self.user1)], 1)
        self.assertEqual(states[(EventTypes.Member, self.user2)], 3)
