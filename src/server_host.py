#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Akinava'
__author_email__ = 'akinava@gmail.com'
__copyright__ = 'Copyright © 2019'
__license__ = 'MIT License'
__version__ = [0, 0]


import asyncio
import settings
from settings import logger
from host import Host
from server_handler import ServerHandler
from server_protocol import PROTOCOL


class Server(Host):
    async def run(self):
        logger.info('')
        self.listener = await self.create_listener(
            (settings.local_host,
             settings.default_port))
        await self.ping()


if __name__ == '__main__':
    logger.info('server start')
    server = Server(handler=ServerHandler, protocol=PROTOCOL)
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info('server interrupted')
    logger.info('server shutdown')
