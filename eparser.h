/*

   Reynir: Natural language processing for Icelandic

   C++ Earley parser module

   Author: Vilhjalmur Thorsteinsson

   This software is at a very early development stage.
   While that is the case, it is:
   Copyright (c) 2015 Vilhjalmur Thorsteinsson
   All rights reserved
   See the accompanying README.md file for further licensing and copyright information.

   This module implements an optimized Earley parser in C++.
   It is designed to be called from Python code with
   already parsed and packed grammar structures.

*/

#include <stdlib.h>
#include <string.h>
#include <wchar.h>


typedef unsigned int UINT;
typedef int INT;
typedef wchar_t WCHAR;
typedef char CHAR;
typedef unsigned char BYTE;
typedef bool BOOL;


class Production;
class Parser;
class State;
class Column;
class NodeDict;
class Label;


class AllocCounter {

   // A utility class to count allocated instances
   // of an instrumented class. Add this as a static
   // member (named e.g. 'ac') of the class to be watched
   // and call ac++ and ac-- in the constructor and destructor,
   // respectively.

private:

   UINT m_nAllocs;
   UINT m_nFrees;

public:

   AllocCounter(void)
      : m_nAllocs(0), m_nFrees(0)
      { }
   ~AllocCounter(void)
      { }

   void operator++(int)
      { this->m_nAllocs++; }
   void operator--(int)
      {
         assert(this->m_nAllocs > this->m_nFrees);
         this->m_nFrees++;
      }
   UINT numAllocs(void) const
      { return this->m_nAllocs; }
   UINT numFrees(void) const
      { return this->m_nFrees; }
   INT getBalance(void) const
      { return (INT)(this->m_nAllocs - this->m_nFrees); }

};


class Nonterminal {

   // A Nonterminal has an associated list of owned Productions

friend class AllocReporter;

private:

   WCHAR* m_pwzName;
   Production* m_pProd;

   static AllocCounter ac;

protected:

public:

   Nonterminal(const WCHAR* pwzName);

   ~Nonterminal(void);

   void addProduction(Production* p);

   // Get the first right-hand-side production of this nonterminal
   Production* getHead(void) const
      { return this->m_pProd; }

   WCHAR* getName(void) const
      { return this->m_pwzName; }

};


class Production {

   // A Production owns a local copy of an array of items,
   // where each item is a negative nonterminal index, or
   // positive terminal index. Attempts to index past the
   // end of the production yield a 0 item.

friend class AllocReporter;

private:

   UINT m_nPriority;       // Relative priority of this production
   UINT m_n;               // Number of items in production
   INT* m_pList;           // List of items in production
   Production* m_pNext;    // Next production of same nonterminal

   static AllocCounter ac;

protected:

public:

   Production(UINT nPriority, UINT n, const INT* pList);

   ~Production(void);

   void setNext(Production* p);
   Production* getNext(void) const
      { return this->m_pNext; }

   UINT getLength(void) const
      { return this->m_n; }
   BOOL isEpsilon(void) const
      { return this->m_n == 0; }
   UINT getPriority(void) const
      { return this->m_nPriority; }

   // Get the item at the dot position within the production
   INT operator[] (UINT nDot) const;

};


class Grammar {

   // A Grammar is a collection of Nonterminals
   // with their Productions.

friend class AllocReporter;

private:

   UINT m_nNonterminals;   // Number of nonterminals
   UINT m_nTerminals;      // Number of terminals (indexed from 1)
   INT m_iRoot;            // Index of root nonterminal (negative)
   Nonterminal** m_nts;    // Array of Nonterminal pointers, owned by the Grammar class

   static AllocCounter ac;

protected:

public:

   Grammar(UINT nNonterminals, UINT nTerminals, INT iRoot = -1);
   Grammar(void);
   ~Grammar(void);

   void reset(void);

   BOOL read_binary(const CHAR* pszFilename);

   UINT getNumNonterminals(void) const
      { return this->m_nNonterminals; }
   UINT getNumTerminals(void) const
      { return this->m_nTerminals; }
   INT getRoot(void) const
      { return this->m_iRoot; }

   void setNonterminal(INT iIndex, Nonterminal*);

   Nonterminal* operator[] (INT iIndex) const;

   const WCHAR* nameOfNt(INT iNt) const;

};


class Label {

   // A Label is associated with a Node.

friend class Node;

private:

   INT m_iNt;
   UINT m_nDot;
   Production* m_pProd;
   UINT m_nI;
   UINT m_nJ;

public:

   Label(INT iNt, UINT nDot, Production* pProd, UINT nI, UINT nJ)
      : m_iNt(iNt), m_nDot(nDot), m_pProd(pProd), m_nI(nI), m_nJ(nJ)
      { }

   BOOL operator==(const Label& other) const
      { return ::memcmp((void*)this, (void*)&other, sizeof(Label)) == 0; }

};


class Node {

friend class AllocReporter;

private:

   struct FamilyEntry {
      Production* pProd;
      Node* p1;
      Node* p2;
      FamilyEntry* pNext;
   };

   Label m_label;
   FamilyEntry* m_pHead;
   UINT m_nRefCount;

   static AllocCounter ac;

   void _dump(Grammar*, UINT nIndent);

protected:

public:

   Node(const Label&);
   ~Node(void);

   void addRef(void)
      { this->m_nRefCount++; }
   void delRef(void);

   void addFamily(Production*, Node* pW, Node* pV);

   BOOL hasLabel(const Label& label) const
      { return this->m_label == label; }

   void dump(Grammar*);

   static UINT numCombinations(Node*);

};


// Token-terminal matching function
typedef BOOL (*MatchingFunc)(UINT nHandle, UINT nToken, UINT nTerminal);

// Default matching function that simply
// compares the token value with the terminal number
BOOL defaultMatcher(UINT nHandle, UINT nToken, UINT nTerminal);


class Parser {

   // Earley-Scott parser for a given Grammar

friend class AllocReporter;

private:

   // Grammar pointer, not owned by the Parser
   Grammar* m_pGrammar;
   MatchingFunc m_pMatchingFunc;

   BOOL _push(UINT nHandle, State*, Column*, State*&);

   Node* _make_node(State* pState, UINT nEnd, Node* pV, NodeDict& ndV);

protected:

public:

   Parser(Grammar*, MatchingFunc = defaultMatcher);
   ~Parser(void);

   UINT getNumTerminals(void) const
      { return this->m_pGrammar->getNumTerminals(); }
   UINT getNumNonterminals(void) const
      { return this->m_pGrammar->getNumNonterminals(); }
   MatchingFunc getMatchingFunc(void) const
      { return this->m_pMatchingFunc; }
   Grammar* getGrammar(void) const
      { return this->m_pGrammar; }

   // If pnToklist is NULL, a sequence of integers 0..nTokens-1 will be used
   Node* parse(UINT nHandle, INT iStartNt, UINT* pnErrorToken,
      UINT nTokens, const UINT pnToklist[] = NULL);

};

// Print a report on memory allocation
extern "C" void printAllocationReport(void);

// Parse a token stream
extern "C" Node* earleyParse(Parser*, UINT nTokens, UINT nHandle, UINT* pnErrorToken);

extern "C" Grammar* newGrammar(const CHAR* pszGrammarFile);

extern "C" void deleteGrammar(Grammar*);

extern "C" Parser* newParser(Grammar*, MatchingFunc fpMatcher = defaultMatcher);

extern "C" void deleteParser(Parser*);

extern "C" void deleteForest(Node*);

extern "C" void dumpForest(Node*, Grammar*);

extern "C" UINT numCombinations(Node*);

