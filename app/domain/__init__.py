"""Robot and map behaviour, free of any knowledge of HTTP or of the API contract.

Declaring the package explicitly keeps it closed: unlike a namespace package, it
cannot silently absorb a directory of the same name found elsewhere on the path.
"""
