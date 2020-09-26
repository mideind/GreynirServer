#!/usr/bin/env python

""" Utility to quickly display profiling information """

import pstats

stats = pstats.Stats("Reynir.profile")

# Clean up filenames for the report
stats.strip_dirs()

# Sort the statistics by the cumulative time spent in a function
#stats.sort_stats('tottime')
stats.sort_stats('cumtime')

stats.print_stats(100) # Print 100 most significant lines

