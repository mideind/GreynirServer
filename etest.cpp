/*

   Reynir: Natural language processing for Icelandic

   C++ Earley parser test program

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


   This module tests the C++ optimized Earley parser.

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

   Production* p0_1 = new Production(0, 0, 1, p0);
   nt4->addProduction(p0_1);
   Production* p1_1 = new Production(1, 0, 1, p1);
   nt1->addProduction(p1_1);
   Production* p1_2 = new Production(2, 0, 2, p2);
   nt1->addProduction(p1_2);
   Production* p2_1 = new Production(3, 0, 3, p3);
   nt2->addProduction(p2_1);
   Production* p3_1 = new Production(4, 0, 2, p4);
   nt3->addProduction(p3_1);
   Production* p5_1 = new Production(5, 0, 1, p5);
   nt5->addProduction(p5_1);
   Production* p5_2 = new Production(6, 0, 0, NULL); // Epsilon
   nt5->addProduction(p5_2);

   pGrammar->setNonterminal(-1, nt1);
   pGrammar->setNonterminal(-2, nt2);
   pGrammar->setNonterminal(-3, nt3);
   pGrammar->setNonterminal(-4, nt4);
   pGrammar->setNonterminal(-5, nt5);
   Parser* pParser = new Parser(pGrammar);

   UINT nErrorToken = 0;

   Node* pNode = pParser->parse(0, -4, &nErrorToken, 9, tokens);

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
   if (!pGrammar->readBinary("Reynir.grammar.bin")) {
      printf("Unable to read binary grammar\n");
      return;
   }
   Parser* pParser = new Parser(pGrammar);

   const UINT tokens[] = {946, 948, 75, 947, 1126, 18, 1055, 20, 9};

   UINT nErrorToken = 0;

   Node* pNode = pParser->parse(0, pGrammar->getRoot(), &nErrorToken, 9, tokens);

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