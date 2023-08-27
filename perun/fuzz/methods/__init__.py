"""Collection of fuzz-testing rules for different types of file.

Currently, we support the following types of rules:
  1. **Binary**: classical rules that can be applied on arbitrary binary stream. The rules comprise,
     e.g. removing bytes, setting or flipping bytes, etc.
  2. **Textfile**: rules inspired by existing performance bugs found in projects focused on text
     files. The rules comprise, e.g. doubling lines (inspired by issues in gedit),
     removing characters (inspired by issues in ReDoS attacks, appending or prepending whitespaces
     (inspired by StackOverflow issues)
  3. **XML**: domain specific rules tuned for XML files currently. These remove parts of the XML
     structure.
"""
