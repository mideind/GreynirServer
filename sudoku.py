"""

Sudoku.py

Sudoku puzzle solver

Copyright (C) 2016 Vilhjalmur Thorsteinsson

"""


import time
from itertools import permutations
from collections import deque, defaultdict

class Conflict(Exception):

    pass

class Puzzle:

    """ A Puzzle instance has a particular dimension, e.g.
        2 for a 4x4 puzzle, 3 for a 9x9 puzzle (the classic Sudoku),
        4 for a 16x16 puzzle or 5 for a 25x25 puzzle.
    """

    # ANSI terminal escape codes to clear the screen and home the cursor
    _HOME = chr(27) + "[H"
    _CLS = chr(27) + "[2J"

    # Show a status update on screen with the given interval
    _STATUS_INTERVAL = 500

    
    class Axis:

        """ Abstract class for the three exclusive axes of a
            Sudoku puzzle, i.e. vertical columns, horizontal rows
            and subsquares. Each axis must end up with exactly one
            instance of each digit. """

        def __init__(self, puzzle):
            """ Each axis consists of (d x d) sets of unassigned digits """
            self._puzzle = puzzle
            SIZE = puzzle.size
            self._size = SIZE
            # The remaining (not yet placed) digits for this axis
            self._set = [ set(puzzle.digits) for _ in range(SIZE) ]

        def has(self, row, col, digit):
            """ Does this axis already have the given digit? """
            assert False # Should be overridden

        def add(self, row, col, digit):
            """ Add the digit to the axis """
            assert False # Should be overridden

        def remove(self, row, col, digit):
            """ Remove the digit from the axis """
            assert False # Should be overridden

        def free_sq(self, index):
            """ Return the first free square on the axis """
            assert False # Should be overridden

        def simplify(self, singles):
            """ Attempt to reduce the possibility sets for this axis, looking for new
                singletons in the process """

            puzzle = self._puzzle
            SIZE = puzzle.size

            # Loop through each component of the axis (each row, column, subsquare)
            for index in range(SIZE):
                possible = set()
                # Dictionary mapping [cardinality -> [possibility set -> [set of squares]]]
                poss_dict = defaultdict(lambda: defaultdict(set))
                for i in range(SIZE):
                    row, col = self.rc(index, i)
                    d = puzzle._sqs[row][col]
                    if d is None:
                        # Empty square
                        poss = puzzle._poss[row][col]
                        lp = len(poss)
                        if lp >= 2:
                            # Store the coordinate by possibility set by cardinality
                            poss_dict[lp][frozenset(poss)].add((row, col))
                        possible |= poss
                    else:
                        possible.add(d)

                if len(possible) < SIZE:
                    # Not all digits are possible: cop out
                    raise Conflict()

                # Now, for each cardinality, check whether we have the
                # same number of squares with an identical possibility set
                # (for example, do we have two squares with the set {2, 5},
                # or three with {1, 7, 8}?)
                # Proceed in order of increasing cardinality
                pd = sorted(poss_dict.items(), key = lambda x: x[0])
                for card, sets in pd:
                    for s, rcset in sets.items():
                        # Add any lower-cardinality sets to this one if
                        # they are contained within this one
                        #for c in range(2, card):
                        #    for c_s, c_rcset in poss_dict[c].items():
                        #        if s >= c_s:
                        #            rcset |= c_rcset
                        if len(rcset) > card:
                            # More squares than there are digits to fill'em with
                            raise Conflict()
                        if len(rcset) == card:
                            # Exactly as many digits as we need to
                            # fill the squares: eliminate the possibility
                            # of these digits from other squares
                            for i in range(SIZE):
                                row, col = self.rc(index, i)
                                if puzzle._sqs[row][col] is None and (row, col) not in rcset:
                                    poss = puzzle._poss[row][col]
                                    if not s.isdisjoint(poss):
                                        poss -= s
                                        if not poss:
                                            # All possibilities gone
                                            raise Conflict()
                                        if len(poss) == 1:
                                            singles.append((row, col, None))

        def find_singles(self, singles):
            """ Check for digits that only occur in one possibility set along the axis """

            puzzle = self._puzzle
            SIZE = puzzle.size

            for index in range(SIZE):
                # For each digit, keep track of whether it occurs in only one
                # possibility set
                digit_singletons = { }
                for i in range(SIZE):
                    row, col = self.rc(index, i)
                    d = puzzle._sqs[row][col]
                    if d is None:
                        # Empty square
                        for d in puzzle._poss[row][col]:
                            if d in digit_singletons:
                                # Seen before: Not a singleton
                                digit_singletons[d] = None
                            else:
                                # May be a singleton: store its index
                                digit_singletons[d] = i
                    else:
                        # The digit is already in a square:
                        # Mark it as a definite non-singleton
                        digit_singletons[d] = None

                for d, i in digit_singletons.items():
                    if i is not None:
                        # This digit occurs only in one possibility set
                        row, col = self.rc(index, i)
                        # print("Found digit singleton {0} at row {1} col {2}".format(d, row, col))
                        singles.append((row, col, d))

        def rc(self, index, i):
            """ Return a (row, column) coordinate within the given component of the axis """
            assert False # Should be overridden

        def __str__(self):
            assert False # Should be overridden

        def remain(self, index):
            """ The count of unfilled (remaining) squares at the indices of this axis """
            return len(self._set[index])

        def missing(self, index):
            """ The set of digits that hasn't been placed on the axis """
            return self._set[index]

        def missing_rc(self, row, col):
            assert False # Should be overridden


    class RowAxis(Axis):

        def has(self, row, col, digit):
            return digit not in self._set[row]

        def add(self, row, col, digit):
            self._set[row].remove(digit)

        def remove(self, row, col, digit):
            self._set[row].add(digit)

        def free_sq(self, index):
            """ Return the first empty square within the given row """
            puzzle = self._puzzle
            return next((index, i) for i in range(self._size) if puzzle._sqs[index][i] is None)

        def rc(self, index, i):
            """ Return a (row, column) coordinate within the given component of the axis """
            return (index, i)

        def missing_rc(self, row, col):
            return self._set[row]

        def __str__(self):
            return "Row"


    class ColAxis(Axis):

        def has(self, row, col, digit):
            return digit not in self._set[col]

        def add(self, row, col, digit):
            self._set[col].remove(digit)

        def remove(self, row, col, digit):
            self._set[col].add(digit)

        def free_sq(self, index):
            """ Return the first empty square within the given column """
            puzzle = self._puzzle
            return next((i, index) for i in range(self._size) if puzzle._sqs[i][index] is None)

        def rc(self, index, i):
            """ Return a (row, column) coordinate within the given component of the axis """
            return (i, index)

        def missing_rc(self, row, col):
            return self._set[col]

        def __str__(self):
            return "Column"


    class SqAxis(Axis):

        """ An axis for the subsquares in the puzzle """

        def __init__(self, puzzle):
            super().__init__(puzzle)
            dimension = self._dimension = puzzle.dimension
            # Create map from (row, col) coordinates to subsquares
            subsq = list()
            ix = 0
            for _ in range(dimension):
                row = list()
                for _ in range(dimension):
                    row.extend([ ix ] * dimension)
                    ix += 1
                for _ in range(dimension):
                    subsq.append(row)
            self._subsq = subsq

            # Create map from (subsquare, index) to (row, col)
            def rc(subsq, index):
                col = (subsq % dimension) * dimension + index % dimension
                row = (subsq // dimension) * dimension + index // dimension
                return (row, col)

            rcmap = list()
            for subsq in range(self._size):
                rcmap.append([ rc(subsq, ix) for ix in range(self._size)])
            self._rcmap = rcmap

        def has(self, row, col, digit):
            subsq = self._subsq[row][col]
            return digit not in self._set[subsq]

        def add(self, row, col, digit):
            subsq = self._subsq[row][col]
            self._set[subsq].remove(digit)

        def remove(self, row, col, digit):
            subsq = self._subsq[row][col]
            self._set[subsq].add(digit)

        def free_sq(self, index):
            """ Return the first empty square within the given subsquare """
            puzzle = self._puzzle
            rcmap = self._rcmap[index]
            return next(rcmap[i] for i in range(self._size) if puzzle.sq(rcmap[i]) is None)

        def rc(self, index, i):
            """ Return a (row, column) coordinate within the given component of the axis """
            return self._rcmap[index][i]

        def missing_rc(self, row, col):
            return self._set[self._subsq[row][col]]

        def __str__(self):
            return "Subsquare"


    def __init__(self, dimension = 3, digits = None):
        # dimension is the square root of the axis length.
        # Thus dimension=3 is a standard 9x9 Sudoku.
        assert 2 <= dimension <= 5
        self._dim = dimension
        self._size = SIZE = dimension * dimension
        if not digits:
            # Use default digit convention
            if dimension <= 3:
                digits = "123456789" [0:SIZE]
            else:
                digits = "ABCDEFGHIJKLMNOPQRSTUVWXY" [0:SIZE]
        assert len(digits) == SIZE
        self._digits = set(digits)
        # Initialize the matrix of squares
        self._sqs = [ [ None for _ in range(SIZE) ] for _ in range(SIZE) ]
        # Initialize the matrix of possible digits
        self._poss = [ [ None for _ in range(SIZE) ] for _ in range(SIZE) ]
        # Initialize the three axes of exclusivity
        self._axes = (
            Puzzle.RowAxis(self),
            Puzzle.ColAxis(self),
            Puzzle.SqAxis(self)
        )
        # Accumulate modifications that may be undone
        self._mods = deque()
        self._counter = 0
    
    @property
    def digits(self):
        return self._digits
    
    @property
    def dimension(self):
        return self._dim
    
    @property
    def size(self):
        return self._size
    
    def sq(self, rc_tuple):
        row, col = rc_tuple
        return self._sqs[row][col]

    def _state(self):
        """ Return a token for the current state """
        return len(self._mods)

    def _pop(self):
        """ Back off from a single add """
        row, col, digit = self._mods.pop()
        self._sqs[row][col] = None
        for axis in self._axes:
            axis.remove(row, col, digit)

    def _restore(self, state):
        """ Pop the puzzle back to a previous state """
        assert state >= 0
        while len(self._mods) > state:
            self._pop()

    def _force_add(self, row, col, digit):
        """ Fill a square in a puzzle with a digit known to be valid """
        self._sqs[row][col] = digit
        for axis in self._axes:
            axis.add(row, col, digit)
        # Note the modification
        self._mods.append((row, col, digit))

    def _try_add(self, row, col, digit):
        """ Fill a square in a puzzle and return True if possible, otherwise return False """
        assert digit in self._digits
        assert 0 <= row < self._size
        assert 0 <= col < self._size
        if self._sqs[row][col] is not None:
            # Already occupied
            return False
        if any(axis.has(row, col, digit) for axis in self._axes):
            # Conflict with another digit
            return False
        self._force_add(row, col, digit)
        return True

    def set(self, s):
        """ Initialize a fresh puzzle from a string """
        if len(s) != self._size * self._size:
            raise ValueError("String to set should be {0} characters; {1} given"
                .format(self._size * self._size, len(s)))

        def gen_digit():
            valid = self.digits | { '.' if ('.' in s) else ' ' }
            for digit in s:
                if digit in valid:
                    yield digit

        gen = gen_digit()
        for row in range(self._size):
            for col in range(self._size):
                digit = next(gen)
                if digit in self.digits:
                    if not self._try_add(row, col, digit):
                        raise ValueError("Column {0} of row {1} cannot contain '{2}'".format(col, row, digit))
        self._mods.clear()

    def __str__(self):
        return "\n".join(
            " ".join((self._sqs[row][col] or " ") for col in range(self._size)) for row in range(self._size)
        )

    def _simplify(self):
        """ Simplify the puzzle by finding the set of possible digits
            for each empty square and fixing the ones that have
            only one place to be. Returns None if the puzzle is
            not consistent, True if it has been solved, or False otherwise. """

        def eliminate_singles(singles):
            """ Fill squares that have only one possible digit """
            fixed = False
            for row, col, d in singles:
                if self._poss[row][col] is not None:
                    possible = tuple(self._poss[row][col])
                    # assert (len(possible) == 1) or (d is not None and d in possible)
                    if not self._try_add(row, col, d or possible[0]):
                        # Conflict between the singles: no solution
                        raise Conflict
                    self._poss[row][col] = None # No need to keep this
                    # Since we now have at least one new fixed digit,
                    # do another loop of simplification
                    fixed = True
            return fixed

        fixed = True
        while fixed:
            fixed = False
            solved = True
            singles = [ ]
            for row in range(self._size):
                for col in range(self._size):
                    if self._sqs[row][col] is None:
                        solved = False
                        # Empty square: initially, all digits are possible
                        possible = set(self._digits)
                        for axis in self._axes:
                            # Cut down the set of possibilities by
                            # AND'ing them with the remaining digits
                            # of each axis in turn
                            possible &= axis.missing_rc(row, col)
                        lp = len(possible)
                        if lp == 0:
                            # Something wrong here: not consistent
                            raise Conflict
                        self._poss[row][col] = possible
                        if lp == 1:
                            # Only one possibility in this square: mark it
                            singles.append((row, col, None))

            fixed = eliminate_singles(singles)

            if not solved and not fixed:
                # Further checks on the possibility sets within each axis
                singles = []
                for axis in self._axes:
                    axis.simplify(singles)
                if not singles:
                    # The possibility sets have been reduced as far as possble:
                    # check for singles, i.e. digits that occur in only one
                    # possibility set
                    for axis in self._axes:
                        axis.find_singles(singles)
                fixed = eliminate_singles(singles)

        return solved

    def _solve(self, depth):
        """ Attempt to solve a puzzle """

        # Start by simplifying the puzzle as far as possible
        state = self._state()

        try:

            if self._simplify():
                # Solved
                return True

            # Find the axis with the fewest remaining unfilled squares

            min_t = None
            for axis in self._axes:
                for index in range(self._size):
                    r = axis.remain(index)
                    if r > 0 and (min_t is None or r < min_t[2]):
                        # New minimum
                        min_t = (axis, index, r)

            axis, index, _ = min_t

            # Show a status update if this puzzle is taking a long time to solve
            self._counter += 1
            if self._counter % Puzzle._STATUS_INTERVAL == 0:
                if self._counter == Puzzle._STATUS_INTERVAL:
                    # First time through: Clear screen
                    print(Puzzle._HOME + Puzzle._CLS, end="")
                print("{1}\nCounter={0} Depth={2}              \n".format(self._counter, Puzzle._HOME, depth))
                print(str(self))

            # Find the first free square in the axis with the fewest
            # such squares; then iterate through all possible digits
            # in that square
            row, col = axis.free_sq(index)

            for digit in tuple(self._poss[row][col]):

                self._force_add(row, col, digit)
                # Try to solve the puzzle recursively as it now stands
                try:
                    if self._solve(depth + 1):
                        # Solution found
                        return True
                except Conflict:
                    pass
                # This doesn't work: take back the last added digit and
                # try the next possibility, if any
                self._pop()

        except Conflict:
            pass

        # If not solved, go back to the original state
        self._restore(state)

        # Gone through all digits that are possible in this unfilled square,
        # without a solution: give up
        return False

    def solve(self):
        """ Attempt to solve the puzzle, returning True if successful """
        return self._solve(0)


def test():

    class Timer:

        total_time = 0.0

    def do_puzzle(dimension, content):
        """ Solve a single puzzle """

        p = Puzzle(dimension = dimension)
        p.set(content)
        print("\nPuzzle to be solved:\n\n{0}".format(p))
        t0 = time.time()
        if p.solve():
            t1 = time.time()
            print("\nPuzzle solution found in {1:.2f} seconds:\n\n{0}".format(p, t1 - t0))
            Timer.total_time += t1 - t0
        else:
            print("\nPuzzle has no solution")

    # Test 'easy' puzzle
    do_puzzle(dimension = 3, content =
        "8 2   3 1"
        "   26148 "
        "47   5 62"
        "    5 1  "
        "  64 85  "
        "  4 7    "
        "54 9   16"
        " 98146   "
        "6 7   2 4"
    )

    # Test 'evil' puzzle
    do_puzzle(dimension = 3, content =
        "  5  7 2 "
        "  81     "
        "  29  7  "
        " 7 3  5 4"
        "         "
        "3 9  5 6 "
        "  6  21  "
        "     94  "
        " 9 5  8  "
    )

    # Test 'evil' puzzle, removing one clue
    do_puzzle(dimension = 3, content =
        "  5  7 2 "
        "  81     "
        "  2   7  "
        " 7 3  5 4"
        "         "
        "3 9  5 6 "
        "  6  21  "
        "     94  "
        " 9 5  8  "
    )

    # Test 'evil' puzzle, adding one random clue
    # that makes it unsolvable
    do_puzzle(dimension = 3, content =
        "  5  7 2 "
        "  81     "
        "  29  7  "
        " 7 3  5 4"
        "    1    "
        "3 9  5 6 "
        "  6  21  "
        "     94  "
        " 9 5  8  "
    )

    do_puzzle(dimension = 3, content =
        "         "
        "8   2   5"
        "     624 "
        " 38  71  "
        "2 4   3 9"
        "  74  52 "
        " 725     "
        "6   8   1"
        "         "
    )

    do_puzzle(dimension = 3, content =
        "  53     "
        "8      2 "
        " 7  1 5  "
        "4    53  "
        " 1  7   6"
        "  32   8 "
        " 6 5    9"
        "  4    3 "
        "     97  "
    )

    do_puzzle(dimension = 3, content =
        '.....6....59.....82....8....45........3........6..3.54...325..6..................'
    )

    # The puzzle below seems to have no solution
    #do_puzzle(dimension = 3, content =
    #    '.....5.8....6.1.43..........1.5........1.6...3.......553.....61........4.........'
    #)

    # Mepham 'diabolical'
    do_puzzle(dimension = 3, content =
        " 9 7  86 "
        " 31  5 2 "
        "8 6      "
        "  7 5   6"
        "   3 7   "
        "5   1 7  "
        "      1 9"
        " 2 6  35 "
        " 54  8 7 "
    )

    # Will Shortz #301
    do_puzzle(dimension = 3, content =
        " 395     "
        "   8   7 "
        "    1 9 4"
        "1  4    3"
        "         "
        "  7   86 "
        "  67 82  "
        " 1  9   5"
        "     1  8"
    )

    #_ = """

    do_puzzle(dimension = 5, content =
        "R   I  EDCM  AH  NX    W "
        "     J ILX     TK  A  P  "
        "O  Q  A     C XMD  EH    "
        "    E N       QB I O    L"
        " SY    MR  DVNI   C  B  E"
        " M BY     REHTO  U K     "
        "V O U    YQ  XC     P  E "
        "  TJ LKDUO GPY S  FR  X M"
        " I X     TB M J  A     V "
        "  F   C  A   W OQHVM Y BS"
        " F  A H     S U TM   NG J"
        "EUJV   BIG  R KHSC Q  W T"
        "D  C S OF  B G LV W      "
        "MW LP  KTJV  HY   DI    B"
        " B Y D    X   E   K     Q"
        " RQUJ T    V  NX FB C   G"
        " V F W RQ  UAK  L     O H"
        " E  L PSCB           A Q "
        " G    X  HW  SRQAPO  FUKY"
        "   TKFG  U  E   JY  IM   "
        "  LST JC  N I   FW   UAM "
        "P     SHKRJO   EC    Q Y "
        "   R  M GWELD    Q   JV  "
        "      I NLAQYVB  R T  CD "
        "  M O   EQT   WK  N FG P "
    )
    #"""

    print("Total time: {0:.2f} seconds".format(Timer.total_time))

if __name__ == "__main__":
    test()
