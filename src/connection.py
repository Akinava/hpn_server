# -*- coding: utf-8 -*-
__author__ = 'Akinava'
__author_email__ = 'akinava@gmail.com'
__copyright__ = 'Copyright © 2019'
__license__ = 'MIT License'
__version__ = [0, 0]


import struct
from time import time
from utilit import Singleton, binary_not
import settings
from settings import logger


class Connection:
    def __init__(self):
        self.set_last_response()

    def __eq__(self, connection):
        if self.remote_host != connection.remote_host:
            return False
        if self.remote_port != connection.remote_port:
            return False
        return True

    def loads(self, connection_data):
        for key, val in connection_data.items():
            if key in ['host', 'port']:
                key = 'remote_{}'.format(key)
            setattr(self, key, val)
        return self

    def is_alive(self):
        if self.transport.is_closing():
            return False
        return True

    def is_time_out(self):
        return time() - self.last_response > settings.peer_timeout_seconds

    def set_last_response(self):
        self.last_response = time()

    def set_transport(self, transport):
        self.transport = transport

    def set_protocol(self, protocol):
        self.protocol = protocol

    def set_local_port(self, local_port):
        self.local_port = local_port

    def get_remote_addr(self):
        return self.remote_host, self.remote_port

    def set_remote_host(self, remote_host):
        self.remote_host = remote_host

    def get_remote_host(self):
        return self.remote_host

    def set_remote_port(self, remote_port):
        self.remote_port = remote_port

    def set_request(self, request):
        self.request = request

    def get_request(self):
        return self.request

    def set_fingerprint(self, fingerprint):
        self.fingerprint = fingerprint

    def get_fingerprint(self):
        return self.fingerprint

    def dump_addr(self):
        return struct.pack('>BBBBH', *(map(int, self.remote_host.split('.'))), self.remote_port)

    def load_addr(self, data):
        port = struct.unpack('>H', data[4:6])
        ip_map = struct.unpack('>BBBB', data[0:4])
        ip = '.'.join(map, ip_map)
        return ip, port

    def set_listener(self, local_port, transport, protocol):
        self.set_protocol(protocol)
        self.set_transport(transport)
        self.set_local_port(local_port)

    def datagram_received(self, request, remote_addr, transport):
        self.set_remote_addr(remote_addr)
        self.set_request(request)
        self.set_transport(transport)

    def set_remote_addr(self, addr):
        self.set_remote_host(addr[0])
        self.set_remote_port(addr[1])

    def send(self, response):
        logger.info('')
        self.transport.sendto(response, (self.remote_host, self.remote_port))

    def shutdown(self):
        self.transport.close()


class NetPool(Singleton):
    def __init__(self):
        self.group_0, self.group_1 = {}, {}

    def __clean_groups(self, group):
        group_alive = []
        for connection in group:
            if connection.is_time_out():
                connection.shutdown()
                continue
            group_alive.append(connection)
        return group_alive

    def __join_groups(self):
        group = {}
        group.update(self.group_0)
        group.update(self.group_1)
        return group

    def __get_connection_param(self, connection):
        return self.group_0.get(connection) or self.group_1.get(connection)

    def __get_connection_group(self, connection):
        if connection in self.group_0:
            return self.group_0
        if connection in self.group_1:
            return self.group_1
        return None

    def __find_waiting_connection(self, connections):
        for connection, params in connections.items():
            if params.get('state') == 'waiting':
                return connection
        return None

    def find_neighbour(self, connection):
        param = self.__get_connection_param(connection)
        connection_groups_index = param.get('groups', set())
        if len(connection_groups_index) != 1:
            connections = self.get_all_connections()
        else:
            connections = self.__get_group_by_index(binary_not(next(iter(connection_groups_index))))
        neighbour_connection = self.__find_waiting_connection(connections)
        return neighbour_connection

    def __get_group_by_index(self, index):
        return getattr(self, 'group_{}'.format(index))

    def save_connection(self, request, remote_addr, transport):
        connection = Connection()
        connection.datagram_received(request, remote_addr, transport)

        if not self.self.__get_connection_group(connection) is None:
            self.__update_connection_in_group(connection)
            return

        self.__put_connection_in_group(connection)

    def __put_connection_in_group(self, connection):
        state = {'state': 'waiting', 'groups': set()}
        if len(self.group_0) > len(self.group_1):
            self.group_1[connection] = state
        else:
            self.group_0[connection] = state

    def __update_connection_in_group(self, connection):
        group = self.__get_connection_group(connection)
        param = self.__get_connection_param(connection)
        param['state'] = 'waiting'
        group[connection] = param

    def get_all_connections(self):
        group_all = self.__join_groups()
        return self.__clean_groups(group_all)

    def update_neighbour_group(self, connection0, connection1):
        if connection0 is None or connection1 is None:
            return
        connection0_group_index = self.self.__get_connection_group_index(connection0)
        connection1_group_index = self.self.__get_connection_group_index(connection1)
        param0 = self.__get_connection_param(connection0)
        param1 = self.__get_connection_param(connection1)
        param0['groups'].add(connection0_group_index)
        param1['groups'].add(connection1_group_index)

    def update_state(self, connection, state):
        param = self.__get_connection_param(connection)
        param['state'] = state

    def __get_connection_group_index(self, connection):
        if connection in self.group_0:
            return 0
        if connection in self.group_1:
            return 1

    def can_be_disconnected(self, connection):
        group = self.__get_connection_group(connection)
        param = self.__get_connection_param(connection)
        connection_groups = param.get('groups', set())
        group_has_enough_connections = len(group) > settings.peer_connections
        connection_connected_to_all_groups  = len(connection_groups) == len(self.group_0, self.group_1)
        return group_has_enough_connections and connection_connected_to_all_groups

    def disconnect(self, connection):
        group = self.__get_connection_group(connection)
        del group[connection]
        connection.shutdown()

    def clean(self):
        for connection, _ in self.__join_groups():
            connection.shutdown()
        self.group_0, self.group_1 = {}, {}
