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

#define DEBUG

#include <stdio.h>
#include <assert.h>

#include "eparser.h"

//  Local implementation classes

class State {

friend class AllocReporter;

private:

   INT m_iNt;              // Nonterminal (negative index)
   Production* m_pProd;    // Production
   UINT m_nDot;            // Dot (position in production)
   UINT m_nStart;          // Start token index
   Node* m_pw;             // Tree node
   State* m_pNext;         // Next state within column
   State* m_pNtNext;       // Next state with same Nt at prod[dot]

   static AllocCounter ac;

protected:

public:

   State(INT iNt, UINT nDot, Production* pProd, UINT nStart, Node* pw);
   State(State*, Node* pw);
   ~State(void);

   void increment(Node* pwNew);

   void setNext(State*);
   void setNtNext(State*);

   State* getNext(void) const
      { return this->m_pNext; }
   State* getNtNext(void) const
      { return this->m_pNtNext; }

   BOOL operator==(const State&) const;

   INT prodDot(void) const
      { return (*this->m_pProd)[this->m_nDot]; }

   INT getNt(void) const
      { return this->m_iNt; }
   UINT getStart(void) const
      { return this->m_nStart; }
   UINT getDot(void) const
      { return this->m_nDot; }
   Production* getProd(void) const
      { return this->m_pProd; }
   Node* getNode(void) const
      { return this->m_pw; }
   Node* getResult(INT iStartNt) const;

};


class Column {

friend class AllocReporter;

private:

   UINT m_nToken;
   State* m_pStates;    // Head of states list
   State* m_pTail;      // Tail of states list
   State** m_pNtStates;

   static AllocCounter ac;

protected:

public:

   Column(Parser*, UINT nToken);
   ~Column(void);

   // Add a state to the column, at the end of the state list
   void addState(State* p);

   State* getHead(void) const
      { return this->m_pStates; }
   State* getNtHead(INT iNt) const;

   BOOL matches(UINT nTerminal) const;

};


class HNode {

   // Represents an element in the H set,
   // corresponding to a completed nullable
   // production of the associated nonterminal

friend class AllocReporter;

private:

   INT m_iNt;
   Node* m_pv;
   HNode* m_pNext;

   static AllocCounter ac;

protected:

public:

   HNode(INT iNt, Node* pv)
      : m_iNt(iNt), m_pv(pv)
      { HNode::ac++; }

   ~HNode()
      { HNode::ac--; }

   INT getNt(void) const
      { return this->m_iNt; }
   Node* getV(void) const
      { return this->m_pv; }
   HNode* getNext(void) const
      { return this->m_pNext; }
   void setNext(HNode* ph)
      { this->m_pNext = ph; }

};

AllocCounter HNode::ac;

class NodeDict {

   // Dictionary to map labels to node pointers

private:

   struct NdEntry {
      Node* pNode;
      NdEntry* pNext;
   };

   NdEntry* m_pHead;

protected:

public:

   NodeDict(void);
   ~NodeDict(void);

   Node* lookupOrAdd(const Label&);

   void reset(void);

};

AllocCounter Nonterminal::ac;

Nonterminal::Nonterminal(const WCHAR* pwzName)
   : m_pwzName(NULL), m_pProd(NULL)
{
   Nonterminal::ac++;
   this->m_pwzName = pwzName ? ::wcsdup(pwzName) : NULL;
}

Nonterminal::~Nonterminal(void)
{
   if (this->m_pwzName)
      free(this->m_pwzName);
   // Delete the associated productions
   Production* p = this->m_pProd;
   while (p) {
      Production* pNext = p->getNext();
      delete p;
      p = pNext;
   }
   Nonterminal::ac--;
}

void Nonterminal::addProduction(Production* p)
{
   // Add a production at the head of the linked list
   p->setNext(this->m_pProd);
   this->m_pProd = p;
}


AllocCounter Production::ac;

Production::Production(UINT n, const INT* pList)
   : m_n(n), m_pList(NULL), m_pNext(NULL)
{
   Production::ac++;
   if (n > 0) {
      this->m_pList = new INT[n];
      ::memcpy((void*)this->m_pList, (void*)pList, n * sizeof(INT));
   }
}

Production::~Production(void) {
   // Destructor
   if (this->m_pList)
      delete [] this->m_pList;
   Production::ac--;
}

void Production::setNext(Production* p)
{
   this->m_pNext = p;
}

INT Production::operator[] (UINT nDot) const
{
   // Return the terminal or nonterminal at prod[dot]
   // or 0 if indexing past the end of the production
   return nDot < this->m_n ? this->m_pList[nDot] : 0;
}


AllocCounter State::ac;

State::State(INT iNt, UINT nDot, Production* pProd, UINT nStart, Node* pw)
   : m_iNt(iNt), m_pProd(pProd), m_nDot(nDot), m_nStart(nStart), m_pw(pw),
      m_pNext(NULL), m_pNtNext(NULL)
{
   State::ac++;
   if (pw)
      pw->addRef();
}

State::State(State* ps, Node* pw)
   : m_iNt(ps->m_iNt), m_pProd(ps->m_pProd), m_nDot(ps->m_nDot + 1),
      m_nStart(ps->m_nStart), m_pw(pw), m_pNext(NULL), m_pNtNext(NULL)
{
   // Create a new state by advancing one item forward from an existing state
   State::ac++;
   if (pw)
      pw->addRef();
}

State::~State(void)
{
   if (this->m_pw)
      this->m_pw->delRef();
   State::ac--;
}

void State::increment(Node* pwNew)
{
   // 'Increment' the state, i.e. move the dot right by one step
   // and put in a new node pointer
   this->m_nDot++;
   this->m_pNext = NULL;
   assert(this->m_pNtNext == NULL);
   if (pwNew)
      pwNew->addRef(); // Do this first, for safety
   if (this->m_pw)
      this->m_pw->delRef();
   this->m_pw = pwNew;
}

BOOL State::operator==(const State& other) const
{
   const State& t = *this;
   return t.m_iNt == other.m_iNt &&
      t.m_pProd == other.m_pProd &&
      t.m_nDot == other.m_nDot &&
      t.m_nStart == other.m_nStart;
}

void State::setNext(State* p)
{
   this->m_pNext = p;
}

void State::setNtNext(State* p)
{
   this->m_pNtNext = p;
}

Node* State::getResult(INT iStartNt) const
{
   if (this->m_iNt == iStartNt && this->prodDot() == 0 &&
      this->m_nStart == 0)
      return this->m_pw;
   return NULL;
}


AllocCounter Column::ac;

Column::Column(Parser* pParser, UINT nToken)
   : m_nToken(nToken), m_pStates(NULL), m_pTail(NULL), m_pNtStates(NULL)
{
   // Initialize array of linked lists by nonterminal at prod[dot]
   Column::ac++;
   UINT nNonterminals = pParser->getNumNonterminals();
   this->m_pNtStates = new State* [nNonterminals];
   ::memset((void*)this->m_pNtStates, 0, nNonterminals * sizeof(State*));
}

Column::~Column(void)
{
   // Delete the states still owned by the column
   State* q = this->m_pStates;
   while (q) {
      State* pNext = q->getNext();
      assert(pNext != NULL || q == this->m_pTail);
      delete q;
      q = pNext;
   }
   this->m_pStates = NULL;
   this->m_pTail = NULL;
   // Delete array of linked lists by nonterminal at prod[dot]
   delete [] this->m_pNtStates;
   Column::ac--;
}

void Column::addState(State* p)
{
   // Check to see whether an identical state is
   // already present in the list
   State* q = this->m_pStates;
   // !!! O(n^2) lookup - add a hash table if this becomes a bottleneck
   while (q) {
      if ((*q) == (*p)) {
         // Identical state: we're done
         delete p;
         return;
      }
      q = q->getNext();
   }
   // Not already found: link into place
   p->setNext(NULL);
   if (!this->m_pStates) {
      // Establish linked list with one item
      this->m_pStates = this->m_pTail = p;
   }
   else {
      // Link the new element at the end
      this->m_pTail->setNext(p);
      this->m_pTail = p;
   }
   // Get the item at prod[dot]
   INT iItem = p->prodDot();
   if (iItem < 0) {
      // Nonterminal: add to linked list
      UINT nIndex = ~((UINT)iItem);
      State*& psHead = this->m_pNtStates[nIndex];
      p->setNtNext(psHead);
      psHead = p;
   }
}

State* Column::getNtHead(INT iNt) const
{
   UINT nIndex = ~((UINT)iNt);
   return this->m_pNtStates[nIndex];
}

BOOL Column::matches(UINT nTerminal) const
{
   if (this->m_nToken == (UINT)-1)
      // Sentinel token in last column: never matches
      return false;
   // !!! Logic to match terminals and tokens goes here
   printf("Column::matches: terminal %u, token %u\n",
      nTerminal, this->m_nToken);
   return this->m_nToken == nTerminal;
}

AllocCounter Grammar::ac;

Grammar::Grammar(UINT nNonterminals, UINT nTerminals)
   : m_nNonterminals(nNonterminals), m_nTerminals(nTerminals), m_nts(NULL)
{
   Grammar::ac++;
   this->m_nts = new Nonterminal*[nNonterminals];
   ::memset((void*)this->m_nts, 0, nNonterminals * sizeof(Nonterminal*));
}

Grammar::~Grammar(void)
{
   for (UINT i = 0; i < this->m_nNonterminals; i++)
      if (this->m_nts[i])
         delete this->m_nts[i];
   delete [] this->m_nts;
   Grammar::ac--;
}

void Grammar::setNonterminal(INT iIndex, Nonterminal* pnt)
{
   // iIndex is negative
   assert(iIndex < 0);
   UINT nIndex = ~((UINT)iIndex); // -1 becomes 0, -2 becomes 1, etc.
   assert(nIndex < this->m_nNonterminals);
   if (nIndex < this->m_nNonterminals)
      this->m_nts[nIndex] = pnt;
}

Nonterminal* Grammar::operator[] (INT iIndex) const
{
   // Return the nonterminal with index nIndex (1-based)
   assert(iIndex < 0);
   UINT nIndex = ~((UINT)iIndex); // -1 becomes 0, -2 becomes 1, etc.
   return (nIndex < this->m_nNonterminals) ? this->m_nts[nIndex] : NULL;
}

const WCHAR* Grammar::nameOfNt(INT iNt) const
{
   Nonterminal* pnt = (*this)[iNt];
   return pnt ? pnt->getName() : L"[None]";
}

AllocCounter Node::ac;

Node::Node(const Label& label)
   : m_label(label), m_pHead(NULL), m_nRefCount(1)
{
   Node::ac++;
}

Node::~Node(void)
{
   FamilyEntry* p = this->m_pHead;
   while (p) {
      FamilyEntry* pNext = p->pNext;
      if (p->p1)
         p->p1->delRef();
      if (p->p2)
         p->p2->delRef();
      delete p;
      p = pNext;
   }
   Node::ac--;
}

void Node::delRef(void)
{
   assert(this->m_nRefCount > 0);
   if (!--this->m_nRefCount)
      delete this;
}

void Node::addFamily(Node* pW, Node* pV)
{
   // pW may be NULL, or both may be NULL if epsilon
   FamilyEntry* p = this->m_pHead;
   while (p) {
      if (p->p1 == pW && p->p2 == pV)
         // We already have the same family entry
         return;
      p = p->pNext;
   }
   // Not already there: create a new entry
   p = new FamilyEntry();
   p->p1 = pW;
   p->p2 = pV;
   if (pW)
      pW->addRef();
   if (pV)
      pV->addRef();
   p->pNext = this->m_pHead;
   this->m_pHead = p;
}

void Node::_dump(Grammar* pGrammar, UINT nIndent)
{
   for (UINT i = 0; i < nIndent; i++)
      printf("  ");
   Production* pProd = this->m_label.m_pProd;
   UINT nDot = this->m_label.m_nDot;
   INT iDotProd = pProd ? (*pProd)[nDot] : 0;
   INT iNt = this->m_label.m_iNt;
   const WCHAR* pwzName;
   WCHAR wchBuf[16];
   if (iNt < 0)
      pwzName = pGrammar->nameOfNt(iNt);
   else {
      swprintf(wchBuf, 16, L"[Token %u]", (UINT)iNt);
      pwzName = wchBuf;
   }
   printf("Label: %ls %u %d %u %u\n",
      pwzName,
      nDot,
      iDotProd,
      this->m_label.m_nI,
      this->m_label.m_nJ);
   FamilyEntry* p = this->m_pHead;
   UINT nOption = 0;
   while(p) {
      if (nOption || p->pNext) {
         // Don't print 'Option 1' if there is only one option
         for (UINT i = 0; i < nIndent; i++)
            printf("  ");
         printf("Option %u\n", nOption + 1);
      }
      if (p->p1)
         p->p1->_dump(pGrammar, nIndent + 1);
      if (p->p2)
         p->p2->_dump(pGrammar, nIndent + 1);
      p = p->pNext;
      nOption++;
   }
}

void Node::dump(Grammar* pGrammar)
{
   this->_dump(pGrammar, 0);
}

NodeDict::NodeDict(void)
   : m_pHead(NULL)
{
}

NodeDict::~NodeDict(void)
{
   this->reset();
}

Node* NodeDict::lookupOrAdd(const Label& label)
{
   // If the label is already found in the NodeDict,
   // return the corresponding node.
   // Otherwise, create a new node, add it to the dict
   // under the label, and return it.
   NdEntry* p = this->m_pHead;
   while (p) {
      if (p->pNode->hasLabel(label))
         return p->pNode;
      p = p->pNext;
   }
   // Not found: add to the dict
   p = new NdEntry();
   p->pNode = new Node(label);
   p->pNext = this->m_pHead;
   this->m_pHead = p;
   return p->pNode;
}

void NodeDict::reset(void)
{
   NdEntry* p = this->m_pHead;
   while (p) {
      NdEntry* pNext = p->pNext;
      p->pNode->delRef();
      delete p;
      p = pNext;
   }
   this->m_pHead = NULL;
}

AllocReporter::AllocReporter(void)
{
}

AllocReporter::~AllocReporter(void)
{
}

void AllocReporter::report(void) const
{
   printf("\nMemory allocation status\n");
   printf("------------------------\n");
   printf("Nonterminals  : %6d %6d\n", Nonterminal::ac.getBalance(), Nonterminal::ac.numAllocs());
   printf("Productions   : %6d %6d\n", Production::ac.getBalance(), Production::ac.numAllocs());
   printf("Grammars      : %6d %6d\n", Grammar::ac.getBalance(), Grammar::ac.numAllocs());
   printf("Nodes         : %6d %6d\n", Node::ac.getBalance(), Node::ac.numAllocs());
   printf("States        : %6d %6d\n", State::ac.getBalance(), State::ac.numAllocs());
   printf("Columns       : %6d %6d\n", Column::ac.getBalance(), Column::ac.numAllocs());
   printf("HNodes        : %6d %6d\n", HNode::ac.getBalance(), HNode::ac.numAllocs());
}


Parser::Parser(Grammar* p)
   : m_pGrammar(p)
{
}

Parser::~Parser(void)
{
}

Node* Parser::_make_node(State* pState, UINT nEnd, Node* pV, NodeDict& ndV)
{
   UINT nDot = pState->getDot() + 1;
   Production* pProd = pState->getProd();
   UINT nLen = pProd->getLength();
   if (nDot == 1 && nLen >= 2)
      return pV;

   INT iNtB = pState->getNt();
   UINT nStart = pState->getStart();
   Node* pW = pState->getNode();
   Production* pProdLabel = pProd;
   if (nDot >= nLen) {
      // Completed production: label by nonterminal only
      nDot = 0;
      pProdLabel = NULL;
   }
   Label label(iNtB, nDot, pProdLabel, nStart, nEnd);
   Node* pY = ndV.lookupOrAdd(label);
   pY->addFamily(pW, pV); // pW may be NULL
   return pY;
}

void Parser::_push(State* pState, Column* pE, State*& pQ)
{
   INT iItem = pState->prodDot();
   if (iItem <= 0)
      // Nonterminal or epsilon: add state to column
      pE->addState(pState);
   else
   if (pE->matches((UINT)iItem)) {
      // Terminal matching the current token
      // Link into list whose head is pQ
      pState->setNext(pQ);
      pQ = pState;
   }
   else
      delete pState;
}

Node* Parser::parse(INT iStartNt, UINT nTokens, const UINT pnToklist[])
{
   // Sanity checks
   if (!nTokens || !pnToklist)
      return NULL;
   if (!this->m_pGrammar)
      return NULL;
   Nonterminal* pRootNt = (*this->m_pGrammar)[iStartNt];
   if (!pRootNt)
      // No or invalid root nonterminal
      return NULL;

   // Initialize the Earley columns
   UINT i;
   Column** pCol = new Column* [nTokens + 1];
   for (i = 0; i < nTokens; i++)
      pCol[i] = new Column(this, pnToklist[i]);
   pCol[i] = new Column(this, (UINT)-1); // Sentinel column

   // Initialize parser state
   State* pQ0 = NULL;

   // Prepare the initial state
   Production* p = pRootNt->getHead();
   while (p) {
      State* ps = new State(iStartNt, 0, p, 0, NULL);
      this->_push(ps, pCol[0], pQ0);
      p = p->getNext();
   }

   // Main parse loop
   State* pQ = NULL;
   NodeDict ndV; // Node dictionary

   for (i = 0; i < nTokens + 1; i++) {

      printf("Column %u, token %u\n", i, (i < nTokens) ? pnToklist[i] : (UINT)-1);

      Column* pEi = pCol[i];
      State* pState = pEi->getHead();

      if (!pState && !pQ0) {
         // No parse available at token i-1
         printf("No parse available at token %u\n", i-1);
         break;
      }

      pQ = pQ0;
      pQ0 = NULL;
      HNode* pH = NULL;

      while (pState) {
         INT iItem = pState->prodDot();
         INT iNtB = pState->getNt();
         UINT nStart = pState->getStart();
         Node* pW = pState->getNode();
         if (iItem < 0) {
            // Earley predictor
            // Push all right hand sides of this nonterminal
            p = (*this->m_pGrammar)[iItem]->getHead();
            while (p) {
               State* psNew = new State(iItem, 0, p, i, NULL);
               this->_push(psNew, pEi, pQ);
               p = p->getNext();
            }
            // Add elements from the H set that refer to the
            // nonterminal iItem (nt_C)
            HNode* ph = pH;
            while (ph) {
               if (ph->getNt() == iItem) {
                  Node* pY = this->_make_node(pState, i, ph->getV(), ndV);
                  State* psNew = new State(pState, pY);
                  this->_push(psNew, pEi, pQ);
               }
               ph = ph->getNext();
            }
         }
         else
         if (iItem == 0) {
            // Earley completer
            if (!pW) {
               Label label(iNtB, 0, NULL, i, i);
               pW = ndV.lookupOrAdd(label);
               pW->addFamily(NULL, NULL); // Epsilon production
            }
            if (nStart == i) {
               HNode* ph = new HNode(iNtB, pW);
               ph->setNext(pH);
               pH = ph;
            }
            State* psNt = pCol[nStart]->getNtHead(iNtB);
            while (psNt) {
               Node* pY = this->_make_node(psNt, i, pW, ndV);
               State* psNew = new State(psNt, pY);
               this->_push(psNew, pEi, pQ);
               psNt = psNt->getNtNext();
            }
         }
         // Move to the next item on the agenda
         // (which may have been enlarged by the previous code)
         pState = pState->getNext();
      }

      // Clean up the H set
      while (pH) {
         HNode* ph = pH->getNext();
         delete pH;
         pH = ph;
      }

      // Reset the node dictionary
      ndV.reset();
      Node* pV = NULL;

      if (pQ) {
         Label label(pnToklist[i], 0, NULL, i, i + 1);
         pV = new Node(label); // Reference is deleted below
      }

      while (pQ) {
         // Earley scanner
         State* psNext = pQ->getNext();
         Node* pY = this->_make_node(pQ, i + 1, pV, ndV);
         // Instead of throwing away the old state and creating
         // a new almost identical one, re-use the old after
         // 'incrementing' it by moving the dot one step to the right
         pQ->increment(pY);
         assert(i + 1 <= nTokens);
         this->_push(pQ, pCol[i + 1], pQ0);
         pQ = psNext;
      }

      // Clean up reference to pV created above
      if (pV)
         pV->delRef();
   }

   assert(pQ == NULL);
   assert(pQ0 == NULL);

   Node* pResult = NULL;
   if (i > nTokens) {
      // Completed the token loop
      State* ps = pCol[nTokens]->getHead();
      while (ps && !pResult) {
         // Look through the end states until we find one that spans the
         // entire parse tree and derives the starting nonterminal
         pResult = ps->getResult(iStartNt);
         if (pResult)
            // Save the result node from being deleted when the
            // column states are deleted
            pResult->addRef();
         ps = ps->getNext();
      }
   }

   // Cleanup
   for (i = 0; i < nTokens + 1; i++)
      delete pCol[i];
   delete [] pCol;

   return pResult; // The caller should call delRef() on this after using it
}


