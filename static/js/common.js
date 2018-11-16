
/*

   Reynir: Natural language processing for Icelandic

   Common.js

   JavaScript utility functions for token display, formatting, etc.

   Copyright (C) 2018 Miðeind ehf.
   Author: Vilhjálmur Þorsteinsson

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

*/

// Token kinds

var TOK_PUNCTUATION = 1;
var TOK_TIME = 2;
var TOK_DATE = 3;
var TOK_YEAR = 4;
var TOK_NUMBER = 5;
var TOK_WORD = 6;
var TOK_TELNO = 7;
var TOK_PERCENT = 8;
var TOK_URL = 9;
var TOK_ORDINAL = 10;
var TOK_TIMESTAMP = 11;
var TOK_CURRENCY = 12;
var TOK_AMOUNT = 13;
var TOK_PERSON = 14;
var TOK_EMAIL = 15;
var TOK_ENTITY = 16;
var TOK_UNKNOWN = 17;
var TOK_DATEABS = 18;
var TOK_DATEREL = 19;
var TOK_TIMESTAMPABS = 20;
var TOK_TIMESTAMPREL = 21;
var TOK_MEASUREMENT = 22;

var tokClass = [];

tokClass[TOK_NUMBER] = "number";
tokClass[TOK_PERCENT] = "percent";
tokClass[TOK_ORDINAL] = "ordinal";
tokClass[TOK_DATE] = "date";
tokClass[TOK_TIMESTAMP] = "timestamp";
tokClass[TOK_CURRENCY] = "currency";
tokClass[TOK_AMOUNT] = "amount";
tokClass[TOK_PERSON] = "person";
tokClass[TOK_ENTITY] = "entity";
tokClass[TOK_YEAR] = "year";
tokClass[TOK_TELNO] = "telno";
tokClass[TOK_EMAIL] = "email";
tokClass[TOK_TIME] = "time";
tokClass[TOK_UNKNOWN] = "nf";
tokClass[TOK_DATEABS] = "dateabs";
tokClass[TOK_DATEREL] = "daterel";
tokClass[TOK_TIMESTAMPABS] = "timestampabs";
tokClass[TOK_TIMESTAMPREL] = "timestamprel";
tokClass[TOK_MEASUREMENT] = "measurement";

var tokId = [];

tokId["PUNCTUATION"] = TOK_PUNCTUATION;
tokId["TIME"] = TOK_TIME;
tokId["DATE"] = TOK_DATE;
tokId["YEAR"] = TOK_YEAR;
tokId["NUMBER"] = TOK_NUMBER;
tokId["WORD"] = TOK_WORD;
tokId["TELNO"] = TOK_TELNO;
tokId["PERCENT"] = TOK_PERCENT;
tokId["URL"] = TOK_URL;
tokId["ORDINAL"] = TOK_ORDINAL;
tokId["TIMESTAMP"] = TOK_TIMESTAMP;
tokId["CURRENCY"] = TOK_CURRENCY;
tokId["AMOUNT"] = TOK_AMOUNT;
tokId["PERSON"] = TOK_PERSON;
tokId["EMAIL"] = TOK_EMAIL;
tokId["ENTITY"] = TOK_ENTITY;
tokId["UNKNOWN"] = TOK_UNKNOWN;
tokId["DATEABS"] = TOK_DATEABS;
tokId["DATEREL"] = TOK_DATEREL;
tokId["TIMESTAMPABS"] = TOK_TIMESTAMPABS;
tokId["TIMESTAMPREL"] = TOK_TIMESTAMPREL;
tokId["MEASUREMENT"] = TOK_MEASUREMENT;

var wordClass = {
   "no" : "óþekkt nafnorð",
   "kk" : "nafnorð",
   "kvk" : "nafnorð",
   "hk" : "nafnorð",
   "so" : "sagnorð",
   "lo" : "lýsingarorð",
   "fs" : "forsetning",
   "st" : "samtenging",
   "stt" : "samtenging",
   "ao" : "atviksorð",
   "spao" : "spurnaratviksorð",
   "tao" : "tímaatviksorð",
   "to" : "töluorð",
   "fn" : "fornafn",
   "pfn" : "persónufornafn",
   "abfn" : "afturbeygt fornafn",
   "gr" : "greinir",
   "nhm" : "nafnháttarmerki",
   "töl" : "töluorð",
   "uh" : "upphrópun",
   "sérnafn" : "sérnafn",
   "gata" : "götuheiti",
   "fyrirtæki" : "fyrirtæki"
};

var variantDesc = [
   { k: "_lh_nt", t : "lýsingarháttur nútíðar", o: 6 },
   { k: "_lhþt", t : "lýsingarháttur þátíðar", o: 6 },
   { k: "_nt", t : "nútíð", o: 0 },
   { k: "_þt", t : "þátíð", o: 0 },
   { k: "_p1", t : "fyrsta persóna", o: 1 },
   { k: "_p2", t : "önnur persóna", o: 1 },
   { k: "_p3", t : "þriðja persóna", o: 1 },
   { k: "_et", t : "eintala", o: 2 },
   { k: "_ft", t : "fleirtala", o: 2 },
   { k: "_kk", t : "karlkyn", o: 3 },
   { k: "_kvk", t : "kvenkyn", o: 3 },
   { k: "_hk", t : "hvorugkyn", o: 3 },
   { k: "_nf", t : "nefnifall", o: 4 },
   { k: "_þf", t : "þolfall", o: 4 },
   { k: "_þgf", t : "þágufall", o: 4 },
   { k: "_ef", t : "eignarfall", o: 4 },
   { k: "_gm", t : "germynd", o: 5 },
   { k: "_mm", t : "miðmynd", o: 5 },
   { k: "_fh", t : "framsöguháttur", o: 6 },
   { k: "_nh", t : "nafnháttur", o: 6 },
   { k: "_bh", t : "boðháttur", o: 6 },
   { k: "_vh", t : "viðtengingarháttur", o: 6 },
   { k: "_sagnb", t : "sagnbót", o: 7 },
   // Ath.: Málfræðin gerir ekki greinarmun á sterkri og veikri beygingu lýsingarorða með nafnorðum
   { k: "_fvb", t : "frumstig<br>veik beyging", o: 9 },
   { k: "_fsb", t : "frumstig<br>sterk beyging", o: 9 },
   { k: "_mst", t : "miðstig", o: 9 },
   { k: "_esb", t : "efsta stig<br>sterk beyging", o: 9 },
   { k: "_evb", t : "efsta stig<br>veik beyging", o: 9 },
   { k: "_sb", t : "sterk beyging", o: 8 },
   { k: "_vb", t : "veik beyging", o: 8 },
   { k: "_gr", t : "með greini", o: 10 }
];

var cases = {
   "nf" : "nefnifalli",
   "þf" : "þolfalli",
   "þgf" : "þágufalli",
   "ef" : "eignarfalli"
};

function format_is(n, decimals) {
   /* Utility function to format a number according to is_IS */
   if (decimals === undefined || decimals < 0)
      decimals = 0;
   var parts = n.toFixed(decimals).split('.');
   parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
   return parts.join(',');
}

function nullFunc(json) {
   /* Null placeholder function to use for Ajax queries that don't need a success func */
}

function nullCompleteFunc(xhr, status) {
   /* Null placeholder function for Ajax completion */
}

function errFunc(xhr, status, errorThrown) {
   /* Default error handling function for Ajax communications */
   // alert("Villa í netsamskiptum");
   console.log("Error: " + errorThrown);
   console.log("Status: " + status);
   console.dir(xhr);
}

function serverQuery(requestUrl, jsonData, successFunc, completeFunc, errorFunc) {
   /* Wraps a simple, standard Ajax request to the server */
   $.ajax({
      // The URL for the request
      url: requestUrl,

      // The data to send
      data: jsonData,

      // Whether this is a POST or GET request
      type: "POST",

      // The type of data we expect back
      dataType : "json",

      cache: false,

      // Code to run if the request succeeds;
      // the response is passed to the function
      success: (!successFunc) ? nullFunc : successFunc,

      // Code to run if the request fails; the raw request and
      // status codes are passed to the function
      error: (!errorFunc) ? errFunc : errorFunc,

      // code to run regardless of success or failure
      complete: (!completeFunc) ? nullCompleteFunc : completeFunc
   });
}

function serverPost(url, parameters, new_window) {
   /* Post to the provided URL with the specified parameters */
   var form = $('<form method="post"></form>');
   form.attr("action", url);
   form.attr("target", new_window ? "_blank" : "_self"); // Display in same or new window
   $.each(parameters, function(key, value) {
      var field = $('<input type="hidden"></input>');
      field.attr("name", key);
      field.attr("value", value);
      form.append(field);
   });
   // The form needs to be a part of the document
   // to allow submission, at least in some browsers
   $(document.body).append(form);
   form.submit();
}

function lzero(n, field) {
   return ("0000000000" + n).slice(-field);
}

function iso_date(d) {
   // Format a date as an ISO string
   // Note: negative years (BCE) are shown as positive
   return lzero(Math.abs(d[0]), 4) + "-" + lzero(d[1], 2) + "-" + lzero(d[2], 2);
}

function iso_time(d) {
   // Format a time as an ISO string
   return lzero(d[0], 2) + ":" + lzero(d[1], 2) + ":" + lzero(d[2], 2);
}

function iso_timestamp(d) {
   // Format a date + time as an ISO string
   // Note: negative years (BCE) are shown as positive
   return lzero(Math.abs(d[0]), 4) + "-" + lzero(d[1], 2) + "-" + lzero(d[2], 2) + " " +
      lzero(d[3], 2) + ":" + lzero(d[4], 2) + ":" + lzero(d[5], 2);
}

function grammar(cat, terminal) {
   var g = [];
   var t = terminal;
   if (t !== undefined) {
      // Use the full terminal specification (e.g. 'so_2_þgf_þf_þt_p3_ft_gm_fh')
      // Look for each feature that we want to document
      $.each(variantDesc, function(ix, val) {
         if (t.indexOf(val.k) > -1) {
            if (cat == "fs") {
               // For prepositions, show "stýrir þágufalli" instead of "þágufall"
               // Avoid special case for "synthetic" prepositions (fs_nh)
               if (val.k !== "_nh")
                  g.push("stýrir " + val.t + "i");
            }
            else
            if (cat !== "so" || "_nf_þf_þgf_ef".indexOf(val.k) < 0)
               // For verbs, skip the cases that they control
               g.push(val.t);
            t = t.replace(val.k, "");
         }
      });
   }
   return g.length ? g.join("<br>") : "";
}

function makePercentGraph(percent) {
   // Adjust progress bar
   $("#percent").css("display", "block");
   $("#percent .progress-bar")
      .attr("aria-valuenow", Math.round(percent).toString())
      .css("width", percent.toString() + "%");
   $("#percent .progress-bar span.sr-only").text(percent.toString() + "%");
}

function tokenInfo(t, nameDict) {
   // Return a dict with information about the given token,
   // including its lemma, grammar info and details
   /*
      t.k: token kind
      t.t: terminal
      t.g: gender (only present if terminal is missing)
      t.m[0]: stofn
      t.m[1]: ordfl
      t.m[2]: fl
      t.m[3]: beyging
      t.x: ordmynd
      t.v: extra info, eventually in a tuple
   */
   var r = {
      class: null,
      tagClass: null,
      lemma: null,
      details: null,
      grammar: null,
      percent: null
   };
   var title;
   var bc;
   var terminal = t.a || t.t; // Use augmented terminal if available
   if (!t.k || t.k == TOK_WORD) {
      // TOK_WORD
      // t.m[1] is the word category (kk, kvk, hk, so, lo...)
      var wcat = (t.m && t.m[1]) ? t.m[1] : (terminal ? terminal.split("_")[0] : undefined);
      if (wcat === undefined)
         // Nothing to show, so we cop out
         return r;
      // Special case: for adverbs, if they match a tao (temporal) or
      // spao (interrogative) adverb terminal, show that information
      if (wcat == "ao" && terminal)
         if (terminal == "tao" || terminal == "spao")
            wcat = terminal;
      var wcls = (wcat && wordClass[wcat]) ? wordClass[wcat] : "óþekkt";
      if (t.m && t.m[1]) {
         r.class = t.m[1];
         // Special case for adverbs: if multi-word adverb phrase,
         // say 'atviksliður' instead of 'atviksorð'
         if (r.class == "ao" && t.m[0].indexOf(" ") > -1)
            wcls = "atviksliður";
         else
         if (r.class == "tao" && t.m[0].indexOf(" ") > -1)
            wcls = "tímaatviksliður";
         else
         if (r.class == "fs" && t.m[0].indexOf(" ") > -1)
            wcls = "fleiryrt forsetning";
         r.grammar = grammar(r.class, terminal);
      }
      r.lemma = (t.m && t.m[0]) ? t.m[0] : t.x;
      r.details = wcls;
   }
   else
   if (t.k == TOK_NUMBER) {
      r.lemma = t.x;
      // Show the parsed floating-point number to 2 decimal places
      r.details = format_is(t.v[0], 2);
   }
   else
   if (t.k == TOK_PERCENT) {
      r.lemma = t.x;
      r.details = "hundraðshluti";
      // Obtain the percentage from token val field (t.v[0]),
      // or from the token text if no such field is available
      var pc = t.v ? t.v[0] : parseFloat(t.x.slice(0, -1).replace(",", "."));
      if (pc === NaN || pc === undefined)
         pc = 0.0;
      r.percent = pc;
   }
   else
   if (t.k == TOK_ORDINAL) {
      r.lemma = t.x;
      if ("0123456789".indexOf(t.x[0]) == -1)
         // Roman numeral
         r.details = "raðtala (" + t.v + ".)";
      else
         r.details = "raðtala";
   }
   else
   if (t.k == TOK_DATE || t.k == TOK_DATEABS) {
      r.lemma = t.x;
      // Show the date in ISO format
      bc = (t.v[0] < 0) ? " f.Kr." : "";
      r.details = "dags. " + iso_date(t.v) + bc;
   }
   else
   if (t.k == TOK_DATEREL) {
      r.lemma = t.x;
      r.details = "afstæð dagsetning";
   }
   else
   if (t.k == TOK_TIME) {
      r.lemma = t.x;
      // Show the time in ISO format
      r.details = "kl. " + iso_time(t.v);
   }
   else
   if (t.k == TOK_YEAR) {
      r.lemma = t.x;
      r.details = "ártal";
   }
   else
   if (t.k == TOK_EMAIL) {
      r.lemma = t.x;
      r.details = "tölvupóstfang";
   }
   else
   if (t.k == TOK_CURRENCY) {
      r.lemma = t.x;
      // Show the ISO code for the currency
      r.details = "gjaldmiðillinn " + t.v[0];
   }
   else
   if (t.k == TOK_AMOUNT) {
      r.lemma = t.x;
      // Show the amount as well as the ISO code for its currency
      r.details = t.v[1] + " " + format_is(t.v[0], 2);
   }
   else
   if (t.k == TOK_PERSON) {
      r.class = "person";
      var gender = "";
      if (t.g) {
         // No associated terminal: There might be a g field with gender information
         if (t.g == "kk")
            gender = "male";
         else
         if (t.g == "kvk")
            gender = "female";
      }
      else
      if (terminal) {
         // Obtain gender info from the associated terminal
         if (terminal.slice(-3) == "_kk")
            gender = "male";
         else
         if (terminal.slice(-4) == "_kvk")
            gender = "female";
      }
      if (gender) {
         r.class += " " + gender;
         r.tagClass = "glyphicon-gender-" + gender;
      }
      if (!t.v || !t.v.length)
         // Cut whitespace around hyphens in person names
         r.lemma = t.x.replace(" - ", "-");
      else {
         // Show full name and title
         var name = t.v;
         title = (nameDict && nameDict[name]) ? (nameDict[name].title || "") : "";
         if (!title.length)
            if (!gender)
               title = "mannsnafn";
            else
               title = (gender == "male") ? "karl" : "kona";
         // Cut whitespace around hyphens in person names
         r.lemma = name.replace(" - ", "-");
         r.details = title;
      }
   }
   else
   if (t.k == TOK_ENTITY) {
      var nd = nameDict ? nameDict[t.x] : undefined;
      if (nd && nd.kind == "ref") {
         // Last name reference to a full name entity
         // ('Clinton' -> 'Hillary Rodham Clinton')
         r.lemma = nd.fullname;
         nd = nameDict[nd.fullname];
      }
      else
         // Cut whitespace around hyphens in entity names
         r.lemma = t.x.replace(" - ", "-");
      title = nd ? (nd.title || "") : "";
      if (!title.length)
         title = "sérnafn";
      r.details = title;
   }
   else
   if (t.k == TOK_TIMESTAMP || t.k == TOK_TIMESTAMPABS) {
      r.lemma = t.x;
      // Show the timestamp in ISO format
      bc = (t.v && t.v[0] < 0) ? " f.Kr." : "";
      r.details = t.v ? (iso_timestamp(t.v) + bc) : "";
   }
   else
   if (t.k == TOK_TIMESTAMPREL) {
      r.lemma = t.x;
      r.details = "afstæð tímasetning";
   }
   else
   if (t.k == TOK_MEASUREMENT) {
      r.lemma = t.x;
      r.details = format_is(t.v[1], 3) + " " + t.v[0]; // Value, unit
   }
   return r;
}

