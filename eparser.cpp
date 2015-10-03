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
#include <stdint.h>
#include <assert.h>

#include "eparser.h"


//  Local implementation classes


class AllocReporter {

   // A debugging aid to diagnose and report memory leaks

private:
protected:
public:

   AllocReporter(void);
   ~AllocReporter(void);

   void report(void) const;

};

void printAllocationReport(void)
{
   AllocReporter reporter;
   reporter.report();
}


class State {

   // Parser state, contained within a Column

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

   UINT getHash(void) const
      {
         return ((UINT)this->m_iNt) ^
            ((UINT)((uintptr_t)this->m_pProd) & 0xFFFFFFFF) ^
            (this->m_nDot << 7) ^ (this->m_nStart << 9) ^
            (((UINT)((uintptr_t)this->m_pw) & 0xFFFFFFFF) << 1);
      }
   BOOL operator==(const State& other) const
      {
         const State& t = *this;
         return t.m_iNt == other.m_iNt &&
            t.m_pProd == other.m_pProd &&
            t.m_nDot == other.m_nDot &&
            t.m_nStart == other.m_nStart &&
            t.m_pw == other.m_pw;
      }

   // Get the terminal or nonterminal at the dot
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

   // An Earley column
   // A Parser cointains one Column for each token in the input, plus a sentinel

friend class AllocReporter;

private:

   // The contained States are stored an array of hash bins

   static const UINT HASH_BINS = 499; // Prime number

   struct HashBin {
      State* m_pHead; // The first state in this hash bin
      State* m_pTail; // The last state in this hash bin
      State* m_pEnum; // The last enumerated state in this hash bin
   };

   UINT m_nToken; // The input token associated with this column
   State** m_pNtStates; // States linked by the nonterminal at their prod[dot]
   MatchingFunc m_pMatchingFunc; // Pointer to the token/terminal matching function
   BYTE* m_abCache; // Matching cache, a true/false flag for every terminal in the grammar
   BYTE* m_abSeen; // Flag whether each nonterminal's productions have already been added
   HashBin m_aHash[HASH_BINS]; // The hash bin array
   UINT m_nEnumBin; // Round robin used during enumeration of states

   static AllocCounter ac;

protected:

public:

   Column(Parser*, UINT nToken);
   ~Column(void);

   UINT getToken(void) const
      { return this->m_nToken; }
   // Add a state to the column, at the end of the state list
   BOOL addState(State* p);

   State* nextState(void);
   void resetEnum(void);

   State* getNtHead(INT iNt) const;
   BOOL markSeen(INT iNt);

   BOOL matches(UINT nHandle, UINT nTerminal) const;

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

Production::Production(UINT nId, UINT nPriority, UINT n, const INT* pList)
   : m_nId(nId), m_nPriority(nPriority), m_n(n), m_pList(NULL), m_pNext(NULL)
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


// States are allocated in chunks, rather than individually
static const UINT CHUNK_SIZE = 2048 * sizeof(State);

struct StateChunk {

   StateChunk* m_pNext;
   UINT m_nIndex;
   BYTE m_ast[CHUNK_SIZE];

   StateChunk(StateChunk* pNext)
      : m_pNext(pNext), m_nIndex(0)
      { memset(this->m_ast, 0, CHUNK_SIZE); }

};

static AllocCounter acChunks;

void* operator new(size_t nBytes, StateChunk*& pChunkHead)
{
   assert(nBytes == sizeof(State));
   // Allocate a new place for a state in a state chunk
   StateChunk* p = pChunkHead;
   if (!p || (p->m_nIndex + nBytes >= CHUNK_SIZE)) {
      StateChunk* pNew = new StateChunk(p);
      acChunks++;
      pChunkHead = p = pNew;
   }
   void* pPlace = (void*)(p->m_ast + p->m_nIndex);
   p->m_nIndex += nBytes;
   assert(p->m_nIndex <= CHUNK_SIZE);
   return pPlace;
}

static void freeStates(StateChunk*& pChunkHead)
{
   StateChunk* pChunk = pChunkHead;
   while (pChunk) {
      StateChunk* pNext = pChunk->m_pNext;
      delete pChunk;
      acChunks--;
      pChunk = pNext;
   }
   pChunkHead = NULL;
}

static UINT nDiscardedStates = 0;

static void discardState(StateChunk* pChunkHead, State* pState)
{
   assert(pChunkHead->m_nIndex >= sizeof(State));
   assert(pChunkHead->m_ast + pChunkHead->m_nIndex - sizeof(State) == (BYTE*)pState);
   pState->~State();
   // Go back one location in the chunk
   pChunkHead->m_nIndex -= sizeof(State);
   nDiscardedStates++;
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
   if (this->m_pw) {
      this->m_pw->delRef();
      this->m_pw = NULL;
   }
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
   : m_nToken(nToken),
      m_pNtStates(NULL),
      m_pMatchingFunc(pParser->getMatchingFunc()),
      m_abCache(NULL),
      m_abSeen(NULL),
      m_nEnumBin(0)
{
   Column::ac++;
   assert(this->m_pMatchingFunc != NULL);
   UINT nNonterminals = pParser->getNumNonterminals();
   UINT nTerminals = pParser->getNumTerminals();
   // Initialize array of linked lists by nonterminal at prod[dot]
   this->m_pNtStates = new State* [nNonterminals];
   memset(this->m_pNtStates, 0, nNonterminals * sizeof(State*));
   // Initialize the matching cache to zero
   this->m_abCache = new BYTE[nTerminals + 1];
   memset(this->m_abCache, 0, (nTerminals + 1) * sizeof(BYTE));
   // Initialize the seen array to zero
   this->m_abSeen = new BYTE[nNonterminals];
   memset(this->m_abSeen, 0, nNonterminals * sizeof(BYTE));
   // Initialize the hash bins to zero
   memset(this->m_aHash, 0, sizeof(HashBin) * HASH_BINS);
}

Column::~Column(void)
{
   // Destroy the states still owned by the column
   for (UINT i = 0; i < HASH_BINS; i++) {
      // Clean up each hash bin in turn
      HashBin* ph = &this->m_aHash[i];
      State* q = ph->m_pHead;
      while (q) {
         State* pNext = q->getNext();
         assert(pNext != NULL || q == ph->m_pTail);
         // The states are allocated via placement new, so
         // they are not deleted ordinarily - we just run their destructor
         q->~State();
         q = pNext;
      }
      ph->m_pHead = NULL;
      ph->m_pTail = NULL;
   }
   // Delete array of linked lists by nonterminal at prod[dot]
   delete [] this->m_pNtStates;
   // Delete matching cache
   delete [] this->m_abCache;
   // Delete seen array
   delete [] this->m_abSeen;
   Column::ac--;
}

BOOL Column::addState(State* p)
{
   // Check to see whether an identical state is
   // already present in the hash bin
   UINT nBin = p->getHash() % HASH_BINS;
   HashBin* ph = &this->m_aHash[nBin];
   State* q = ph->m_pHead;
   while (q) {
      if ((*q) == (*p))
         // Identical state: we're done
         return false;
      q = q->getNext();
   }
   // Not already found: link into place within the hash bin
   p->setNext(NULL);
   if (!ph->m_pHead) {
      // Establish linked list with one item
      ph->m_pHead = ph->m_pTail = p;
   }
   else {
      // Link the new element at the tail
      ph->m_pTail->setNext(p);
      ph->m_pTail = p;
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
   return true;
}

State* Column::nextState(void)
{
   // Start our enumeration attempt from the last bin we looked at
   UINT n = this->m_nEnumBin;
   do {
      HashBin* ph = &this->m_aHash[n];
      if (!ph->m_pEnum && ph->m_pHead) {
         // Haven't enumerated from this one before,
         // but it has an entry: return it
         ph->m_pEnum = ph->m_pHead;
         this->m_nEnumBin = n;
         return ph->m_pEnum;
      }
      // Try the next item after the one we last returned
      State* pNext = ph->m_pEnum ? ph->m_pEnum->getNext() : NULL;
      if (pNext) {
         // There is such an item: return it
         ph->m_pEnum = pNext;
         this->m_nEnumBin = n;
         return pNext;
      }
      // Can't enumerate any more from this bin: go to the next one
      n = (n + 1) % HASH_BINS;
   } while (n != this->m_nEnumBin);
   // Gone full circle: Nothing more to enumerate
   return NULL;
}

void Column::resetEnum(void)
{
   // Start a fresh enumeration
   for (UINT i = 0; i < HASH_BINS; i++)
      this->m_aHash[i].m_pEnum = NULL;
   this->m_nEnumBin = 0;
}

State* Column::getNtHead(INT iNt) const
{
   UINT nIndex = ~((UINT)iNt);
   return this->m_pNtStates[nIndex];
}

BOOL Column::matches(UINT nHandle, UINT nTerminal) const
{
   if (this->m_nToken == (UINT)-1)
      // Sentinel token in last column: never matches
      return false;
   if (this->m_abCache[nTerminal] & 0x80)
      // We already have a cached result for this terminal
      return (BOOL)(this->m_abCache[nTerminal] & 0x01);
   // Not cached: obtain a result and store it in the cache
   BOOL b = this->m_pMatchingFunc(nHandle, this->m_nToken, nTerminal) != 0;
   // Mark our cache
   this->m_abCache[nTerminal] = b ? (BYTE)0x81 : (BYTE)0x80;
   return b;
}

BOOL Column::markSeen(INT iNt)
{
   // Guard to ensure that each nonterminal is only added once to the column
   assert(iNt < 0);
   UINT nIndex = ~((UINT)iNt);
   BOOL b = this->m_abSeen[nIndex] == 0;
   this->m_abSeen[nIndex] = 1;
   return b;
}


class File {

   // Safe wrapper for FILE*

private:

   FILE* m_f;

public:

   File(const CHAR* pszFilename, const CHAR* pszMode)
      { this->m_f = fopen(pszFilename, pszMode); }
   ~File(void)
      { if (this->m_f) fclose(this->m_f); }

   operator FILE*() const
      { return this->m_f; }
   operator BOOL() const
      { return this->m_f != NULL; }

   UINT read(void* pb, UINT nLen)
      { return this->m_f ? fread(pb, 1, nLen, this->m_f) : 0; }
   UINT write(void* pb, UINT nLen)
      { return this->m_f ? fwrite(pb, 1, nLen, this->m_f) : 0; }

   BOOL read_UINT(UINT& n)
      { return this->read(&n, sizeof(UINT)) == sizeof(UINT); }
   BOOL read_INT(INT& i)
      { return this->read(&i, sizeof(INT)) == sizeof(INT); }

};


AllocCounter Grammar::ac;

Grammar::Grammar(UINT nNonterminals, UINT nTerminals, INT iRoot)
   : m_nNonterminals(nNonterminals), m_nTerminals(nTerminals), m_iRoot(iRoot), m_nts(NULL)
{
   Grammar::ac++;
   this->m_nts = new Nonterminal*[nNonterminals];
   memset(this->m_nts, 0, nNonterminals * sizeof(Nonterminal*));
}

Grammar::Grammar(void)
   : m_nNonterminals(0), m_nTerminals(0), m_iRoot(0), m_nts(NULL)
{
   Grammar::ac++;
}

Grammar::~Grammar(void)
{
   this->reset();
   Grammar::ac--;
}

void Grammar::reset(void)
{
   for (UINT i = 0; i < this->m_nNonterminals; i++)
      if (this->m_nts[i])
         delete this->m_nts[i];
   if (this->m_nts) {
      delete [] this->m_nts;
      this->m_nts = NULL;
   }
   this->m_nNonterminals = 0;
   this->m_nTerminals = 0;
   this->m_iRoot = 0;
}

class GrammarResetter {

   // Resets a grammar to a known zero state unless
   // explicitly disarmed

private:

   Grammar* m_pGrammar;

public:

   GrammarResetter(Grammar* pGrammar)
      : m_pGrammar(pGrammar)
      { }
   ~GrammarResetter(void)
      { if (this->m_pGrammar) this->m_pGrammar->reset(); }

   void disarm(void)
      { this->m_pGrammar = NULL; }

};

BOOL Grammar::read_binary(const CHAR* pszFilename)
{
   // Attempt to read grammar from binary file.
   // Returns true if successful, otherwise false.
   printf("Reading binary grammar file %s\n", pszFilename);
   this->reset();
   File f(pszFilename, "rb");
   if (!f)
      return false;
   const UINT SIGNATURE_LENGTH = 16;
   BYTE abSignature[SIGNATURE_LENGTH];
   UINT n = f.read(abSignature, sizeof(abSignature));
   if (n < sizeof(abSignature))
      return false;
   // Check the signature - should start with 'Reynir '
   if (memcmp(abSignature, "Reynir ", 7) != 0) {
      printf("Signature mismatch\n");
      return false;
   }
   UINT nNonterminals, nTerminals;
   if (!f.read_UINT(nTerminals))
      return false;
   if (!f.read_UINT(nNonterminals))
      return false;
   printf("Reading %u terminals and %u nonterminals\n", nTerminals, nNonterminals);
   if (!nNonterminals)
      // No nonterminals to read: we're done
      return true;
   INT iRoot;
   if (!f.read_INT(iRoot))
      return false;
   printf("Root nonterminal index is %d\n", iRoot);
   // Initialize the nonterminals array
   Nonterminal** ppnts = new Nonterminal*[nNonterminals];
   memset(ppnts, 0, nNonterminals * sizeof(Nonterminal*));
   this->m_nts = ppnts;
   this->m_nNonterminals = nNonterminals;
   this->m_nTerminals = nTerminals;
   this->m_iRoot = iRoot;
   // Ensure we clean up properly in case of exit with error
   GrammarResetter resetter(this);
   // Loop through the nonterminals
   for (n = 0; n < nNonterminals; n++) {
      // How many productions?
      UINT nLenPlist;
      if (!f.read_UINT(nLenPlist))
         return false;
      Nonterminal* pnt = new Nonterminal(L"");
      // Loop through the productions
      for (UINT j = 0; j < nLenPlist; j++) {
         UINT nId;
         if (!f.read_UINT(nId))
            return false;
         UINT nPriority;
         if (!f.read_UINT(nPriority))
            return false;
         UINT nLenProd;
         if (!f.read_UINT(nLenProd))
            return false;
         const UINT MAX_LEN_PROD = 256;
         if (nLenProd > MAX_LEN_PROD) {
            // Production too long
            printf("Production too long\n");
            return false;
         }
         // Read the production
         INT aiProd[MAX_LEN_PROD];
         f.read(aiProd, nLenProd * sizeof(INT));
         // Create a fresh production object
         Production* pprod = new Production(nId, nPriority, nLenProd, aiProd);
         // Add it to the nonterminal
         pnt->addProduction(pprod);
      }
      // Add the nonterminal to the grammar
      this->setNonterminal(-1 -(INT)n, pnt);
   }
   printf("Reading completed\n");
   // No error: we disarm the resetter
   resetter.disarm();
   fflush(stdout);
   return true;
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

void Node::addFamily(Production* pProd, Node* pW, Node* pV)
{
   // pW may be NULL, or both may be NULL if epsilon
   FamilyEntry* p = this->m_pHead;
   while (p) {
      if (p->pProd == pProd && p->p1 == pW && p->p2 == pV)
         // We already have the same family entry
         return;
      p = p->pNext;
   }
   // Not already there: create a new entry
   p = new FamilyEntry();
   p->pProd = pProd;
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
   if (iNt < 0) {
      // Nonterminal
      pwzName = pGrammar->nameOfNt(iNt);
      if (!pwzName || wcslen(pwzName) == 0) {
         swprintf(wchBuf, 16, L"[Nt %d]", iNt);
         pwzName = wchBuf;
      }
   }
   else {
      // Token
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
   while (p) {
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
   fflush(stdout);
}

void Node::dump(Grammar* pGrammar)
{
   this->_dump(pGrammar, 0);
}

UINT Node::numCombinations(Node* pNode)
{
   if (!pNode || pNode->m_label.m_iNt >= 0)
      return 1;
   UINT nComb = 0;
   FamilyEntry* p = pNode->m_pHead;
   while (p) {
      UINT n1 = p->p1 ? Node::numCombinations(p->p1) : 1;
      UINT n2 = p->p2 ? Node::numCombinations(p->p2) : 1;
      nComb += n1 * n2;
      p = p->pNext;
   }
   return nComb == 0 ? 1 : nComb;
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


Parser::Parser(Grammar* p, MatchingFunc pMatchingFunc)
   : m_pGrammar(p), m_pMatchingFunc(pMatchingFunc)
{
   assert(this->m_pGrammar != NULL);
   assert(this->m_pMatchingFunc != NULL);
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
   pY->addFamily(pProd, pW, pV); // pW may be NULL
   return pY;
}

BOOL Parser::_push(UINT nHandle, State* pState, Column* pE, State*& pQ)
{
   INT iItem = pState->prodDot();
   if (iItem <= 0)
      // Nonterminal or epsilon: add state to column
      return pE->addState(pState);
   if (pE->matches(nHandle, (UINT)iItem)) {
      // Terminal matching the current token
      // Link into list whose head is pQ
      pState->setNext(pQ);
      pQ = pState;
      return true;
   }
   // Return false to indicate that we did not take ownership of the State
   return false;
}

Node* Parser::parse(UINT nHandle, INT iStartNt, UINT* pnErrorToken,
   UINT nTokens, const UINT pnToklist[])
{
   // If pnToklist is NULL, a sequence of integers 0..nTokens-1 will be used
   // Sanity checks
   if (pnErrorToken)
      *pnErrorToken = 0;
   if (!nTokens)
      return NULL;
   if (!this->m_pGrammar)
      return NULL;
   if (iStartNt >= 0)
      // Root must be nonterminal (index < 0)
      return NULL;
   Nonterminal* pRootNt = (*this->m_pGrammar)[iStartNt];
   if (!pRootNt)
      // No or invalid root nonterminal
      return NULL;

   // Initialize the Earley columns
   UINT i;
   Column** pCol = new Column* [nTokens + 1];
   for (i = 0; i < nTokens; i++)
      pCol[i] = new Column(this, pnToklist ? pnToklist[i] : i);
   pCol[i] = new Column(this, (UINT)-1); // Sentinel column

   // Initialize parser state
   State* pQ0 = NULL;
   StateChunk* pChunkHead = NULL;

   // Prepare the initial state
   Production* p = pRootNt->getHead();
   while (p) {
      State* ps = new (pChunkHead) State(iStartNt, 0, p, 0, NULL);
      if (!this->_push(nHandle, ps, pCol[0], pQ0))
         discardState(pChunkHead, ps);
      p = p->getNext();
   }

   // Main parse loop
   State* pQ = NULL;
   NodeDict ndV; // Node dictionary

   for (i = 0; i < nTokens + 1; i++) {

      Column* pEi = pCol[i];
      State* pState = pEi->nextState();

      // printf("Column %u, token %u\n", i, pEi->getToken());

      if (!pState && !pQ0) {
         // No parse available at token i-1
         if (pnErrorToken)
            *pnErrorToken = i;
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
            // Don't push the same nonterminal more than once to the same column
            if (pEi->markSeen(iItem)) {
               // Earley predictor
               // Push all right hand sides of this nonterminal
               p = (*this->m_pGrammar)[iItem]->getHead();
               while (p) {
                  State* psNew = new (pChunkHead) State(iItem, 0, p, i, NULL);
                  if (!this->_push(nHandle, psNew, pEi, pQ))
                     discardState(pChunkHead, psNew);
                  p = p->getNext();
               }
            }
            // Add elements from the H set that refer to the
            // nonterminal iItem (nt_C)
            HNode* ph = pH;
            while (ph) {
               if (ph->getNt() == iItem) {
                  Node* pY = this->_make_node(pState, i, ph->getV(), ndV);
                  State* psNew = new (pChunkHead) State(pState, pY);
                  if (!this->_push(nHandle, psNew, pEi, pQ))
                     discardState(pChunkHead, psNew);
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
               pW->addFamily(pState->getProd(), NULL, NULL); // Epsilon production
            }
            if (nStart == i) {
               HNode* ph = new HNode(iNtB, pW);
               ph->setNext(pH);
               pH = ph;
            }
            State* psNt = pCol[nStart]->getNtHead(iNtB);
            while (psNt) {
               Node* pY = this->_make_node(psNt, i, pW, ndV);
               State* psNew = new (pChunkHead) State(psNt, pY);
               if (!this->_push(nHandle, psNew, pEi, pQ))
                  discardState(pChunkHead, psNew);
               psNt = psNt->getNtNext();
            }
         }
         // Move to the next item on the agenda
         // (which may have been enlarged by the previous code)
         pState = pEi->nextState();
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
         Label label(pEi->getToken(), 0, NULL, i, i + 1);
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
         if (!this->_push(nHandle, pQ, pCol[i + 1], pQ0))
            pQ->~State();
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
      pCol[nTokens]->resetEnum();
      State* ps = pCol[nTokens]->nextState();
      while (ps && !pResult) {
         // Look through the end states until we find one that spans the
         // entire parse tree and derives the starting nonterminal
         pResult = ps->getResult(iStartNt);
         if (pResult)
            // Save the result node from being deleted when the
            // column states are deleted
            pResult->addRef();
         ps = pCol[nTokens]->nextState();
      }
      if (!pResult && pnErrorToken)
         // No parse available at the last column
         *pnErrorToken = nTokens;
   }

   // Cleanup
   for (i = 0; i < nTokens + 1; i++)
      delete pCol[i];
   delete [] pCol;

   freeStates(pChunkHead);

   return pResult; // The caller should call delRef() on this after using it
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
   printf("Nonterminals : %6d %8d\n", Nonterminal::ac.getBalance(), Nonterminal::ac.numAllocs());
   printf("Productions  : %6d %8d\n", Production::ac.getBalance(), Production::ac.numAllocs());
   printf("Grammars     : %6d %8d\n", Grammar::ac.getBalance(), Grammar::ac.numAllocs());
   printf("Nodes        : %6d %8d\n", Node::ac.getBalance(), Node::ac.numAllocs());
   printf("States       : %6d %8d\n", State::ac.getBalance(), State::ac.numAllocs());
   printf("...discarded : %6s %8d\n", "", nDiscardedStates);
   printf("StateChunks  : %6d %8d\n", acChunks.getBalance(), acChunks.numAllocs());
   printf("Columns      : %6d %8d\n", Column::ac.getBalance(), Column::ac.numAllocs());
   printf("HNodes       : %6d %8d\n", HNode::ac.getBalance(), HNode::ac.numAllocs());
   fflush(stdout); // !!! Debugging
}


// The functions below are declared extern "C" for external invocation
// of the parser (e.g. from CFFI)

// Token-terminal matching function
BOOL defaultMatcher(UINT nHandle, UINT nToken, UINT nTerminal)
{
   // printf("defaultMatcher(): token is %u, terminal is %u\n", nToken, nTerminal);
   return nToken == nTerminal;
}

Grammar* newGrammar(const CHAR* pszGrammarFile)
{
   if (!pszGrammarFile)
      return NULL;
   // Read grammar from binary file
   Grammar* pGrammar = new Grammar();
   if (!pGrammar->read_binary(pszGrammarFile)) {
      printf("Unable to read binary grammar file %s\n", pszGrammarFile);
      delete pGrammar;
      return NULL;
   }
   return pGrammar;
}

void deleteGrammar(Grammar* pGrammar)
{
   if (pGrammar)
      delete pGrammar;
}

Parser* newParser(Grammar* pGrammar, MatchingFunc fpMatcher)
{
   if (!pGrammar || !fpMatcher)
      return NULL;
   return new Parser(pGrammar, fpMatcher);
}

void deleteParser(Parser* pParser)
{
   if (pParser)
      delete pParser;
}

void deleteForest(Node* pNode)
{
   if (pNode)
      pNode->delRef();
}

void dumpForest(Node* pNode, Grammar* pGrammar)
{
   if (pNode && pGrammar)
      pNode->dump(pGrammar);
}

UINT numCombinations(Node* pNode)
{
   return pNode ? Node::numCombinations(pNode) : 0;
}

Node* earleyParse(Parser* pParser, UINT nTokens, UINT nHandle, UINT* pnErrorToken)
{
   // Preparation and sanity checks
   if (pnErrorToken)
      *pnErrorToken = 0;
   if (!pParser)
      return NULL;
   if (!nTokens)
      return NULL;
   if (!pParser->getGrammar())
      return NULL;

   // Run parser from the default root
   INT iRoot = pParser->getGrammar()->getRoot();
   assert(iRoot < 0); // Must be a nonterminal

   Node* pNode = pParser->parse(nHandle, iRoot, pnErrorToken, nTokens);

   return pNode;
}


