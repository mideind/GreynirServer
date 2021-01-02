/*   Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

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

"use strict";

var BATCH_SIZE = 10;
var batches = [];
var batch_queue = [];
var sent_map = {};
var pg_map = {};
var is_translating = false;

function hoverInTranslation(ev) {
   var sId = $(this).parent().attr("id");
   if (sId === null || sId === undefined || !sent_map || !sId.startsWith("trnsl")) {
      // No id: nothing to do
      return;
   }
   var offset = $(this).position();
   height = $(this).outerHeight();
   bottom = offset.top + height;
   sent_idx = sId.replace("trnsl", "");
   $("#info-trnsl").html(sent_map[sent_idx]["is"]);
   // Position the info popup
   $("#info-trnsl")
      .css("top", bottom + "px")
      .css("left", offset.left.toString() + "px")
      .css("visibility", "visible");
}

function hoverOutTranslation() {
   $("#info-trnsl").css("visibility", "hidden").html("");
}

function wait_translation(state) {
   // Start or stop a wait spinner when awaiting translation
   // True means spinner is active
   if (state) {
      $("#spinner").show();
   } else {
      $("#spinner").hide();
   }
}

function extract_segmented_paragraphs(pgs_obj) {
   /* Extract article text and segment into paragraphs
      and sentences returns:
         map of
            map from sentence_id to sent_obj
            map from pgs_id to array of sent_obj */
   var pg_map = {};
   var sent_map = {};
   var sent_idx = 1;
   $.each(pgs_obj, function(pg_cursor, pg_obj) {
      pg_map[pg_cursor] = [];
      $.each(pg_obj, function(sent_cursor, sent_obj) {
         var toks = [];
         $.each(sent_obj, function(tok_cursor, tok_obj) {
            if (tok_obj.hasOwnProperty("x")) {
               toks.push(tok_obj.x);
            }
         });
         sent_map[sent_idx] = {
            is: toks.join(" ")
         };
         pg_map[pg_cursor].push(sent_idx);
         sent_idx++;
      });
   });
   return {
      "pg_map": pg_map,
      "sent_map": sent_map
   };
}

function populateTargets(pg_map, sent_map) {
   var pg_container = $("div#result-translation");
   $.each(pg_map, function(pg_idx, sent_key) {
      var pg_elem = $("<p></p>");
      $.each(pg_map[pg_idx], function(sent_cursor, sent_idx) {
         var sent_elem = $("<i></i>", {
            "text": sent_map[sent_idx]["is"]
         });
         var sent_container = $("<span></span>", {
            "id": "trnsl" + sent_idx,
            "class": "sent"
         });
         sent_container.append(sent_elem);
         pg_elem.append(sent_container);
      });
      pg_container.append(pg_elem);
   });
   $("div#result-translation i").hover(hoverInTranslation, hoverOutTranslation);
}

function make_batches(sent_map, batch_size) {
   var parseIntDec = function(str) {
      return parseInt(str, 10);
   };
   var cmpInt = function(a, b) {
      return a - b;
   };
   var isInt = function(n) {
      return !isNaN(n);
   };
   var idxs = Object.keys(sent_map)
      .map(parseIntDec)
      .filter(isInt)
      .sort(cmpInt);
   var batches = [];
   var batch = {};
   var idx = 0;
   var count = 0;
   while (idx < idxs.length) {
      if (count < batch_size) {
         if (sent_map[idx].hasOwnProperty("en")) {
            idx++;
            continue;
         }
         batch[idx] = sent_map[idx]["is"];
         idx++;
         count++;
      } else {
         batches.push(batch);
         batch = {};
         count = 0;
      }
   }
   if (count > 0) {
      batches.push(batch);
   }
   return batches;
}

function translateNext() {
   if (batch_queue.length > 0 && is_translating) {
      var batch_idx = batch_queue.pop();
      var batch = batches[batch_idx];
      translateBatch(batch, translateNext);
   } else {
      wait_translation(false);
   }
}

function translateBatch(batch, callback) {
   serverJsonQuery("/nntranslate.api", // Endpoint with .api suffix are not cached
      {
         pgs: batch,
         src_lang: "is",
         tgt_lang: "en",
      },
      function handleSuccess(json) {
         results = json.result.results;
         populateBatchResults(results, callback);
         wait_translation(false);
      },
      null,
      function handleError(json) {
         console.log(json);
         wait_translation(false);
      }
   );
}

function populateBatchResults(results, callback) {
   $.each(results, function(sent_key, obj) {
      outputs = obj.outputs;
      inputs = obj.inputs;
      scores = obj.scores;
      score_class = scoreClass(scores);
      if (sent_key !== "0") {
         // we need to handle article title seperately
         sent_map[sent_key]["is"] = inputs;
         sent_map[sent_key]["en"] = outputs;
         sent_map[sent_key]["scores"] = scores;
         $("#trnsl" + sent_key).addClass("translated " + score_class)
            .children("i")
            .eq(0)
            .text(outputs);
      } else {
         // replace article head
         $("#meta-heading").text(obj.outputs);
      }
   });
   callback();
}

function scoreClass(_score) {
   score = parseFloat(_score);
   if (score <= -8.5) {
      return "bad err";
   } else if (score <= -4.0) {
      return "average";
   } else {
      return "good";
   }
}

function doTranslation() {
   // Submit the contents of the article incrementally
   // to the server for translation
   if ($.isEmptyObject(sent_map)) {
      wait_translation(true);
      var pg_seg = extract_segmented_paragraphs(j);
      pg_map = pg_seg["pg_map"];
      sent_map = pg_seg["sent_map"];
      var a_title = $("#meta-heading").text();
      sent_map[0] = a_title;
      populateTargets(pg_map, sent_map);
      batches = make_batches(sent_map, BATCH_SIZE);
      batch_queue = Array.from(Array(batches.length).keys()).reverse();
      is_translating = true;
      translateNext();
   } else {
      is_translating = true;
      batches = make_batches(sent_map, BATCH_SIZE);
      batch_queue = Array.from(Array(batches.length).keys()).reverse();
      translateNext();
   }
}

function showOriginalArticle() {
   if (!$.isEmptyObject(sent_map)) {
      is_translating = false;
      $("#meta-heading").text(sent_map[0]);
   }
}
