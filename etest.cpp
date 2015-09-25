/*

   Reynir: Natural language processing for Icelandic

   C++ Earley parser test program

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

#include <stdio.h>
#include <locale.h>
#include <assert.h>

#include "eparser.h"

void runTest_1(void)
{
   /*
      S0 -> Setning
      Setning -> Yrðing | Setning OgSetning
      Yrðing -> nafnorð sagnorð Atviksorð
      OgSetning -> og Setning
      Atviksorð -> atviksorð | 0
   */
   const int p0[] = {-1};
   const int p1[] = {-2};
   const int p2[] = {-1, -3};
   const int p3[] = {1, 2, -5};
   const int p4[] = {3, -1};
   const int p5[] = {4};

   const UINT tokens[] = {1, 2, 3, 1, 2, 4, 3, 1, 2};

   Grammar* pGrammar = new Grammar(5, 4); // Nonterminals, terminals

   Nonterminal* nt4 = new Nonterminal(L"S0");
   Nonterminal* nt1 = new Nonterminal(L"Setning");
   Nonterminal* nt2 = new Nonterminal(L"Yrðing");
   Nonterminal* nt3 = new Nonterminal(L"OgSetning");
   Nonterminal* nt5 = new Nonterminal(L"Atviksorð");

   Production* p0_1 = new Production(0, 1, p0);
   nt4->addProduction(p0_1);
   Production* p1_1 = new Production(0, 1, p1);
   nt1->addProduction(p1_1);
   Production* p1_2 = new Production(0, 2, p2);
   nt1->addProduction(p1_2);
   Production* p2_1 = new Production(0, 3, p3);
   nt2->addProduction(p2_1);
   Production* p3_1 = new Production(0, 2, p4);
   nt3->addProduction(p3_1);
   Production* p5_1 = new Production(0, 1, p5);
   nt5->addProduction(p5_1);
   Production* p5_2 = new Production(0, 0, NULL); // Epsilon
   nt5->addProduction(p5_2);

   pGrammar->setNonterminal(-1, nt1);
   pGrammar->setNonterminal(-2, nt2);
   pGrammar->setNonterminal(-3, nt3);
   pGrammar->setNonterminal(-4, nt4);
   pGrammar->setNonterminal(-5, nt5);
   Parser* pParser = new Parser(pGrammar);

   Node* pNode = pParser->parse(-4, 9, tokens);

   if (!pNode)
      printf("No tree returned\n");
   else {
      pNode->dump(pGrammar);
      // Delete the final reference to the result node
      pNode->delRef();
      pNode = NULL;
   }

   delete pParser;
   delete pGrammar;

   // Report memory allocation
   printAllocationReport();
}

void runTest_2(void)
{
   // Read grammar from binary file
   Grammar* pGrammar = new Grammar();
   if (!pGrammar->read_binary("Reynir.grammar.bin")) {
      printf("Unable to read binary grammar\n");
      return;
   }
   Parser* pParser = new Parser(pGrammar);

   const UINT tokens[] = {946, 948, 75, 947, 1126, 18, 1055, 20, 9};

   Node* pNode = pParser->parse(pGrammar->getRoot(), 9, tokens);

   if (!pNode)
      printf("No tree returned\n");
   else {
      pNode->dump(pGrammar);
      // Delete the final reference to the result node
      pNode->delRef();
      pNode = NULL;
   }

   delete pParser;
   delete pGrammar;

   // Report memory allocation
   printAllocationReport();
}

int main(int argc, char* argv[]) {
   printf("Eparser test starting\n");
   setlocale(LC_ALL, "is_IS.UTF-8");
   runTest_1();
   runTest_2();
   printf("Eparser test done\n");
}