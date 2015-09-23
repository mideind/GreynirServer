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
typedef bool BOOL;


class Production;
class Parser;
class State;
class Column;
class NodeDict;
class Label;


class AllocReporter {

   // A debugging aid to diagnose memory leaks

private:
protected:
public:

   AllocReporter(void);
   ~AllocReporter(void);

   void report(void) const;

};

class AllocCounter {

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

   UINT m_n;               // Number of items in production
   INT* m_pList;           // List of items in production
   Production* m_pNext;    // Next production of same nonterminal

   static AllocCounter ac;

protected:

public:

   Production(UINT n, const INT* pList);

   ~Production(void);

   void setNext(Production* p);
   Production* getNext(void) const
      { return this->m_pNext; }

   UINT getLength(void) const
      { return this->m_n; }
   BOOL isEpsilon(void) const
      { return this->m_n == 0; }

   // Get the item at the dot position within the production
   INT operator[] (UINT nDot) const;

};


class Grammar {

friend class AllocReporter;

private:

   UINT m_nNonterminals;   // Number of nonterminals
   UINT m_nTerminals;      // Number of terminals (indexed from 1)
   Nonterminal** m_nts;    // Array of Nonterminal pointers, owned by the Grammar class

   static AllocCounter ac;

protected:

public:

   Grammar(UINT nNonterminals, UINT nTerminals);
   ~Grammar(void);

   UINT getNumNonterminals(void) const
      { return this->m_nNonterminals; }

   void setNonterminal(INT iIndex, Nonterminal*);

   Nonterminal* operator[] (INT iIndex) const;

   const WCHAR* nameOfNt(INT iNt) const;

};


class Label {

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

   void addFamily(Node* pW, Node* pV);

   BOOL hasLabel(const Label& label) const
      { return this->m_label == label; }

   void dump(Grammar*);

};


class Parser {

private:

   // Grammar pointer, not owned by the Parser
   Grammar* m_pGrammar;

   void _push(State*, Column*, State*&);

   Node* _make_node(State* pState, UINT nEnd, Node* pV, NodeDict& ndV);

protected:

public:

   Parser(Grammar*);
   ~Parser(void);

   UINT getNumNonterminals(void) const
      { return this->m_pGrammar->getNumNonterminals(); }

   Node* parse(INT iStartNt, UINT nTokens, const UINT pnToklist[]);

};

