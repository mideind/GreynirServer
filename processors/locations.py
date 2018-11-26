#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Processor module to extract entity names & definitions

    Copyright (C) 2016 Vilhjálmur Þorsteinsson

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module implements a processor that looks at parsed sentence trees
    and extracts any addresses / locations, looks up information about
    them and saves to a database.

"""

from iceaddr import iceaddr_lookup
from tree import Node

def article_begin(state):
    """ Called at the beginning of article processing """

    # Delete all existing persons for this article
	# session = state["session"] # Database session
	# url = state["url"] # URL of the article being processed
    #session.execute(Person.table().delete().where(Person.article_url == url))

def article_end(state):
    """ Called at the end of article processing """
    pass

def sentence(state, result):
    """ Called at the end of sentence processing """
    pass

def Heimilisfang(node, params, result):
	from pprint import pprint
	pprint(result._nominative)
	pprint(result._state['url'])
	pprint(result._node.contained_text())

	#exit()