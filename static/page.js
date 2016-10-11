
/*

   Page.js

   Scripts for displaying tokenized and parsed text,
   with pop-up tags on hover, name registry, statistics, etc.

   Author: Vilhjalmur Thorsteinsson
   Copyright (C) 2016
   All rights reserved

   For details about the token JSON format, see Article._dump_tokens() in article.py.
   t.x is original token text.
   t.k is the token kind (TOK_x). If omitted, this is TOK_WORD.
   t.t is the name of the matching terminal, if any.
   t.m is the BÍN meaning of the token, if any, as a tuple as follows:
      t.m[0] is the lemma (stofn)
      t.m[1] is the word category (ordfl)
      t.m[2] is the word subcategory (fl)
      t.m[3] is the word meaning/declination (beyging)
   t.v contains auxiliary information, depending on the token kind
   t.err is 1 if the token is an error token

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

var wordClass = {
   "no" : "óþekkt nafnorð",
   "kk" : "nafnorð",
   "kvk" : "nafnorð",
   "hk" : "nafnorð",
   "so" : "sagnorð",
   "lo" : "lýsingarorð",
   "fs" : "forsetning",
   "st" : "samtenging",
   "ao" : "atviksorð",
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

var grammarDesc = [
   { k: "LH-NT", t : "lýsingarháttur nútíðar", o: 6 },
   { k: "LHÞT", t : "lýsingarháttur þátíðar", o: 6 },
   { k: "NT", t : "nútíð", o: 0 },
   { k: "ÞT", t : "þátíð", o: 0 },
   { k: "1P", t : "fyrsta persóna", o: 1 },
   { k: "2P", t : "önnur persóna", o: 1 },
   { k: "3P", t : "þriðja persóna", o: 1 },
   { k: "ET", t : "eintala", o: 2 },
   { k: "FT", t : "fleirtala", o: 2 },
   { k: "KK", t : "karlkyn", o: 3 },
   { k: "KVK", t : "kvenkyn", o: 3 },
   { k: "HK", t : "hvorugkyn", o: 3 },
   { k: "NF", t : "nefnifall", o: 4 },
   { k: "ÞF", t : "þolfall", o: 4 },
   { k: "ÞGF", t : "þágufall", o: 4 },
   { k: "EF", t : "eignarfall", o: 4 },
   { k: "GM", t : "germynd", o: 5 },
   { k: "MM", t : "miðmynd", o: 5 },
   { k: "NH", t : "nafnháttur", o: 6 },
   { k: "BH", t : "boðháttur", o: 6 },
   { k: "VH", t : "viðtengingarháttur", o: 6 },
   { k: "SAGNB", t : "sagnbót", o: 7 },
   // Ath.: Málfræðin gerir ekki greinarmun á sterkri og veikri beygingu lýsingarorða með nafnorðum
   { k: "FVB", t : "frumstig", o: 9 },
   { k: "FSB", t : "frumstig", o: 9 },
   { k: "MST", t : "miðstig", o: 9 },
   { k: "ESB", t : "efsta stig", o: 9 },
   { k: "EVB", t : "efsta stig", o: 9 },
   { k: "SB", t : "sterk beyging", o: 8 },
   { k: "VB", t : "veik beyging", o: 8 },
   { k: "gr", t : "með greini", o: 10 }
];

// Punctuation types

var TP_LEFT = 1;
var TP_CENTER = 2;
var TP_RIGHT = 3;
var TP_NONE = 4; // Tight - no whitespace around
var TP_WORD = 5;

// Token spacing

var TP_SPACE = [
    // Next token is:
    // LEFT    CENTER  RIGHT   NONE    WORD
    // Last token was TP_LEFT:
    [ false,  true,   false,  false,  false],
    // Last token was TP_CENTER:
    [ true,   true,   true,   true,   true],
    // Last token was TP_RIGHT:
    [ true,   true,   false,  false,  true],
    // Last token was TP_NONE:
    [ false,  true,   false,  false,  false],
    // Last token was TP_WORD:
    [ true,   true,   false,  false,  true]
];

var LEFT_PUNCTUATION = "([„«#$€<";
var RIGHT_PUNCTUATION = ".,:;)]!%?“»”’…°>";
var NONE_PUNCTUATION = "—–-/'~‘\\";
// CENTER_PUNCTUATION = '"*&+=@©|'

// Words array
var w = [];

// Name dictionary
var nameDict = { };

function debugMode() {
   return false;
}

function format_is(n, decimals) {
   /* Utility function to format a number according to is_IS */
   if (decimals === undefined || decimals < 0)
      decimals = 0;
   var parts = n.toFixed(decimals).split('.');
   parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
   return parts.join(',');
}

function spacing(t) {
   // Determine the spacing requirements of a token
   if (t.k != TOK_PUNCTUATION)
      return TP_WORD;
   if (LEFT_PUNCTUATION.indexOf(t.x) > -1)
      return TP_LEFT;
   if (RIGHT_PUNCTUATION.indexOf(t.x) > -1)
      return TP_RIGHT;
   if (NONE_PUNCTUATION.indexOf(t.x) > -1)
      return TP_NONE;
   return TP_CENTER;
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

function queryPerson(name) {
   // Navigate to the main page with a person query
   window.location.href = "/?f=q&q=" + encodeURIComponent("Hver er " + name + "?");
}

function queryEntity(name) {
   // Navigate to the main page with an entity query
   window.location.href = "/?f=q&q=" + encodeURIComponent("Hvað er " + name + "?");
}

function showParse(ev) {
   // A sentence has been clicked: show its parse grid
   var sentText = $(ev.delegateTarget).text();
   // Do an HTML POST to the parsegrid URL, passing
   // the sentence text within a synthetic form
   serverPost("/parsegrid", { txt: sentText, debug: debugMode() }, false)
}

function showPerson(ev) {
   // Send a query to the server
   var name = undefined;
   var wId = $(this).attr("id"); // Check for token id
   if (wId !== undefined) {
      // Obtain the name in nominative case from the token
      var ix = parseInt(wId.slice(1));
      if (w[ix] !== undefined)
         name = w[ix].v;
   }
   if (name === undefined)
      name = $(this).text(); // No associated token: use the contained text
   queryPerson(name);
   ev.stopPropagation();
}

function showEntity(ev) {
   // Send a query to the server
   var ename = $(this).text();
   var nd = nameDict[ename];
   if (nd && nd.kind == "ref")
      // Last name reference to a full name entity
      // ('Clinton' -> 'Hillary Rodham Clinton')
      // In this case, we assume that we're asking about a person
      queryPerson(nd.fullname);
   else
      queryEntity(ename);
   ev.stopPropagation();
}

function lzero(n, field) {
   return ("0000000000" + n).slice(-field);
}

function iso_date(d) {
   // Format a date as an ISO string
   return lzero(d[0], 4) + "-" + lzero(d[1], 2) + "-" + lzero(d[2], 2);
}

function iso_time(d) {
   // Format a time as an ISO string
   return lzero(d[0], 2) + ":" + lzero(d[1], 2) + ":" + lzero(d[2], 2);
}

function iso_timestamp(d) {
   // Format a date + time as an ISO string
   return lzero(d[0], 4) + "-" + lzero(d[1], 2) + "-" + lzero(d[2], 2) + " " +
      lzero(d[3], 2) + ":" + lzero(d[4], 2) + ":" + lzero(d[5], 2);
}

function grammar(cat, m) {
   var g = [];
   var gender = { "kk" : "karlkyn", "kvk" : "kvenkyn", "hk" : "hvorugkyn" } [cat];
   if (gender !== undefined)
      g.push(gender);
   $.each(grammarDesc, function(ix, val) {
      if (m.indexOf(val.k) > -1) {
         if (cat == "fs")
            // For prepositions, show "stýrir þágufalli" instead of "þágufall"
            g.push("stýrir " + val.t + "i");
         else
            g.push(val.t);
         m = m.replace(val.k, "");
      }
   });
   return g.join("<br>");
}

function makePercentGraph(percent) {
   // Adjust progress bar
   $("#percent").css("display", "block");
   $("#percent .progress-bar")
      .attr("aria-valuenow", Math.round(percent).toString())
      .css("width", percent.toString() + "%");
   $("#percent .progress-bar span.sr-only").text(percent.toString() + "%");
/*
   // Draw a simple bar graph using D3 with SVG
   $("#grammar").html("<svg class='gpercent'></svg>");
   var width = 134,
      height = 16;

   var x = d3.scale.linear()
      .domain([0, 100])
      .range([0, width])
      .clamp(true);

   var chart = d3.select(".gpercent")
      .attr("width", width)
      .attr("height", height);

   var bar = chart.selectAll("g")
      .data([ percent ])
   .enter().append("g")
      .attr("transform", "translate(0,0)");

   bar.append("rect")
      .attr("class", "gbackground")
      .attr("width", width)
      .attr("height", height);

   bar.append("rect")
      .attr("width", function(d) { return x(d); })
      .attr("height", height);
/*
   bar.append("text")
      .attr("x", 5)
      .attr("y", height / 2)
      .attr("dy", ".35em")
      .text(function(d) { return format_is(d, 1) + "%"; });
*/
}

function hoverIn() {
   // Hovering over a token
   var wId = $(this).attr("id");
   var offset = $(this).position();
   var info = $("div.info");
   if (wId === null || wId === undefined)
      // No id: nothing to do
      return;
   var ix = parseInt(wId.slice(1));
   var t = w[ix];
   if (!t)
      return;

   // Highlight the token
   $(this).addClass("highlight");
   $("#grammar").html("");
   // Hide the percentage bar
   $("#percent").css("display", "none");

   if (!t.k) {
      // TOK_WORD
      var wcat = t.m ? t.m[1] : (t.t ? t.t.split("_")[0] : undefined);
      if (wcat === undefined)
         // Nothing to show, so we cop out
         return;
      var wcls = (wcat && wordClass[wcat]) ? wordClass[wcat] : "óþekkt";
      if (t.m) {
         info.addClass(t.m[1]);
         // Special case for adverbs: if multi-word adverb phrase,
         // say 'atviksliður' instead of 'atviksorð'
         if (t.m[1] == "ao" && t.m[0].indexOf(" ") > -1)
            wcls = "atviksliður";
         $("#grammar").html(grammar(t.m[1], t.m[3]));
      }
      $("#lemma").text(t.m ? t.m[0] : t.x);
      $("#details").text(wcls);
   }
   else
   if (t.k == TOK_NUMBER) {
      $("#lemma").text(t.x);
      // Show the parsed floating-point number to 2 decimal places
      $("#details").text(format_is(t.v[0], 2));
   }
   else
   if (t.k == TOK_PERCENT) {
      $("#lemma").text(t.x);
      $("#details").text("hundraðshluti");
      // Obtain the percentage from token val field (t.v[0]),
      // or from the token text if no such field is available
      var pc = t.v ? t.v[0] : parseFloat(t.x.slice(0, -1).replace(",", "."));
      if (pc === NaN || pc === undefined)
         pc = 0.0;
      makePercentGraph(pc);
   }
   else
   if (t.k == TOK_ORDINAL) {
      $("#lemma").text(t.x);
      $("#details").text("raðtala");
   }
   else
   if (t.k == TOK_DATE) {
      $("#lemma").text(t.x);
      // Show the date in ISO format
      $("#details").text("dags. " + iso_date(t.v));
   }
   else
   if (t.k == TOK_TIME) {
      $("#lemma").text(t.x);
      // Show the time in ISO format
      $("#details").text("kl. " + iso_time(t.v));
   }
   else
   if (t.k == TOK_YEAR) {
      $("#lemma").text(t.x);
      $("#details").text("ártal");
   }
   else
   if (t.k == TOK_EMAIL) {
      $("#lemma").text(t.x);
      $("#details").text("tölvupóstfang");
   }
   else
   if (t.k == TOK_CURRENCY) {
      $("#lemma").text(t.x);
      // Show the ISO code for the currency
      $("#details").text("gjaldmiðillinn " + t.v[0]);
   }
   else
   if (t.k == TOK_AMOUNT) {
      $("#lemma").text(t.x);
      // Show the amount as well as the ISO code for its currency
      $("#details").text(t.v[1] + " " + format_is(t.v[0], 2));
   }
   else
   if (t.k == TOK_PERSON) {
      info.addClass("person");
      var gender = "";
      if (t.t) {
         // Obtain gender info from the associated terminal
         if (t.t.slice(-3) == "_kk")
            gender = "male";
         else
         if (t.t.slice(-4) == "_kvk")
            gender = "female";
      }
      else
      if (t.g) {
         // No associated terminal: There might be a g field with gender information
         if (t.g == "kk")
            gender = "male";
         else
         if (t.g == "kvk")
            gender = "female";
      }
      if (gender) {
         info.addClass(gender);
         $("div.info span#tag")
            .removeClass("glyphicon-tag")
            .addClass("glyphicon-gender-" + gender);
      }
      if (!t.v.length)
         $("#lemma").text(t.x);
      else {
         // Show full name and title
         var name = t.v;
         var title = (nameDict && nameDict[name]) ? (nameDict[name].title || "") : "";
         if (!title.length)
            if (!gender)
               title = "mannsnafn";
            else
               title = (gender == "male") ? "karl" : "kona";
         $("#lemma").text(name);
         $("#details").text(title);
      }
   }
   else
   if (t.k == TOK_ENTITY) {
      var nd = nameDict[t.x];
      if (nd && nd.kind == "ref") {
         // Last name reference to a full name entity
         // ('Clinton' -> 'Hillary Rodham Clinton')
         $("#lemma").text(nd.fullname);
         nd = nameDict[nd.fullname];
      }
      else
         $("#lemma").text(t.x);
      var title = nd ? (nd.title || "") : "";
      if (!title.length)
         title = "sérnafn";
      $("#details").text(title);
   }
   else
   if (t.k == TOK_TIMESTAMP) {
      $("#lemma").text(t.x);
      // Show the timestamp in ISO format
      $("#details").text(iso_timestamp(t.v));
   }
   // Position the info popup
   info
      .css("top", offset.top.toString() + "px")
      .css("left", offset.left.toString() + "px")
      .css("visibility", "visible");
}

function hoverOut() {
   // Stop hovering over a word
   var info = $("div.info");
   info.css("visibility", "hidden");
   $(this).removeClass("highlight");
   var wId = $(this).attr("id");
   if (wId === null || wId === undefined)
      // No id: nothing more to do
      return;
   var ix = parseInt(wId.slice(1));
   var t = w[ix];
   if (!t)
      return;
   if (!t.k && t.m)
      info.removeClass(t.m[1]);
   else
   if (t.k == TOK_PERSON) {
      // Reset back to the original state
      info
         .removeClass("person")
         .removeClass("male")
         .removeClass("female");
      $("div.info span#tag")
         .removeClass("glyphicon-gender-male")
         .removeClass("glyphicon-gender-female")
         .addClass("glyphicon-tag");
   }
}

function displayTokens(j) {
   var x = ""; // Result text
   var lastSp;
   w = [];
   if (j !== null)
      $.each(j, function(pix, p) {
         // Paragraph p
         x += "<p>\n";
         $.each(p, function(six, s) {
            // Sentence s
            var err = false;
            lastSp = TP_NONE;
            // Check whether the sentence has an error or was fully parsed
            $.each(s, function(tix, t) {
               if (t.err == 1) {
                  err = true;
                  return false; // Break the iteration
               }
            });
            if (err)
               x += "<span class='sent err'>";
            else
               x += "<span class='sent parsed'>";
            $.each(s, function(tix, t) {
               // Token t
               var thisSp = spacing(t);
               // Insert a space in front of this word if required
               // (but never at the start of a sentence)
               if (TP_SPACE[lastSp - 1][thisSp - 1] && tix)
                  x += " ";
               lastSp = thisSp;
               if (t.err)
                  // Mark an error token
                  x += "<span class='errtok'>";
               if (t.k == TOK_PUNCTUATION)
                  x += (t.x == "—") ? " — " : t.x; // Space around em-dash
               else {
                  var cls;
                  if (!t.k) {
                     // TOK_WORD
                     if (err)
                        cls = "";
                     else
                     if (t.m)
                        // Word class (noun, verb, adjective...)
                        cls = " class='" + t.m[1] + "'";
                     else
                     if (t.t && t.t.split("_")[0] == "sérnafn")
                        cls = " class='entity'";
                     else
                        // Not found
                        cls = " class='nf'";
                  }
                  else
                     cls = " class='" + tokClass[t.k] + "'";
                  x += "<i id='w" + w.length + "'" + cls + ">" + t.x + "</i>";
                  // Append to word/token list
                  w.push(t);
               }
               if (t.err)
                  x += "</span>";
            });
            // Finish sentence
            x += "</span>\n";
         });
         // Finish paragraph
         x += "</p>\n";
      });
   // Show the page text
   $("div#result").html(x);
   // Put a hover handler on each word
   $("div#result i").hover(hoverIn, hoverOut);
   // Put a click handler on each sentence
   $("span.sent").click(showParse);
   // Separate click handler on entity names
   $("i.entity").click(showEntity);
   // Separate click handler on person names
   $("i.person").click(showPerson);
}

function populateStats(stats) {
   $("#tok-num").text(format_is(stats.num_tokens));
   $("#num-sent").text(format_is(stats.num_sentences));
   $("#num-parsed-sent").text(format_is(stats.num_parsed));
   if (stats.num_sentences > 0)
      $("#num-parsed-ratio").text(format_is(100.0 * stats.num_parsed / stats.num_sentences, 1));
   else
      $("#num-parsed-ratio").text("0.0");
   $("#avg-ambig-factor").text(format_is(stats.ambiguity, 2));
   $("div#statistics").css("display", "block");
}

function populateRegister() {
   // Populate the name register display
   var i, item, name, title;
   var register = [];
   $("#namelist").html("");
   $.each(nameDict, function(name, desc) {
      // kind is 'ref', 'name' or 'entity'
      if (desc.kind != "ref")
         // We don't display references to full names
         register.push({ name: name, title: desc.title, kind: desc.kind });
   });
   register.sort(function(a, b) {
      return a.name.localeCompare(b.name);
   });
   for (i = 0; i < register.length; i++) {
      var ri = register[i];
      item = $("<li></li>");
      name = $("<span></span>").addClass(ri.kind).text(ri.name);
      title = $("<span></span>").addClass("title").text(ri.title);
      item.append(name);
      item.append(title);
      $("#namelist").append(item);
   }
   // Display the register
   if (register.length) {
      $("#register").css("display", "block");
      $("#namelist span.name").click(function(ev) {
         // Send a person query to the server
         queryPerson($(this).text());
      });
      $("#namelist span.entity").click(function(ev) {
         // Send an entity query to the server
         queryEntity($(this).text());
      });
   }
}

