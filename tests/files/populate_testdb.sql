/* 
    Populate database tables with dummy data. 
*/

INSERT INTO articles ("url", "id", "root_id", "heading", "author", "timestamp", "authority", "scraped", "parsed", "processed", "indexed", "scr_module", "scr_class", "scr_version", "parser_version", "num_sentences", "num_parsed", "ambiguity", "html", "tree", "tokens", "topic_vector") VALUES
('https://greynir.is/', '2f1963a4-34fe-11e9-a615-3200174ea5c0', 3, 'Grein', 'Höfundur', '2019-02-20 07:00:00', 0.8, '2019-02-20 10:56:51.362325', '2019-02-20 11:02:24.189203', '2019-02-20 16:25:32.738527', '2019-04-17 15:23:21.808573', 'scrapers.default', 'VisirScraper', '1.0', '2019-02-14 11:41:47/1.0/1.0', 9, 8, 1.61813453744468, '', '', '', '');

INSERT INTO persons ("id", "article_url", "name", "title", "title_lc", "gender", "authority", "timestamp") VALUES
(1, 'https://greynir.is/', 'Björn Þorsteinsson', 'prófessor í heimspeki', 'prófessor í heimspeki', 'kk', 1, '2019-02-11 13:44:41.635725'),
(2, 'https://greynir.is/', 'Viðar Þorsteinsson', 'framkvæmdastjóri Eflingar', 'framkvæmdastjóri eflingar', 'kk', 1, '2019-02-11 13:44:41.992479'),
(3, 'https://greynir.is/', 'Katrín Jakobsdóttir', 'forsætisráðherra', 'forsætisráðherra', 'kvk', 1, '2019-02-11 13:44:41.994941'),
(4, 'https://greynir.is/', 'Jón Jónsson', 'forstjóri Sjóvá', 'forstjóri sjóvá', 'kk', 1, '2019-02-11 13:44:41.994941');

INSERT INTO entities ("id", "article_url", "name", "verb", "definition", "authority", "timestamp") VALUES
(4319412, 'https://greynir.is/', 'Nox Medical', 'er', 'nýsköpunarfyrirtæki', 0.8, '2018-08-26 07:07:50.688911');

INSERT INTO queries ("id", "timestamp", "interpretations", "question", "bquestion", "answer", "voice", "error", "expires", "qtype", "key", "client_type", "client_version", "client_id", "latitude", "longitude", "remote_addr", "context") VALUES
('c619a8ec-72c2-11ea-99c0-820d5d3a9700', '2020-03-30 20:12:25.985256', '["hver er forsætisráðherra"]', 'hver er forsætisráðherra', 'Hver er forsætisráðherra?', 'Katrín Jakobsdóttir', 'Forsætisráðherra er Katrín Jakobsdóttir.', NULL, NULL, 'Title', 'forsætisráðherra', NULL, NULL, '123', NULL, NULL, '127.0.0.1', '{"person_name": "Katrín Jakobsdóttir"}'),
('c9c84304-72c2-11ea-99c0-820d5d3a9700', '2020-03-30 20:12:31.749396', '["hvað segir wikipedia um hana"]', 'hvað segir wikipedia um hana', 'Hvað segir Wikipedía um Hana?', 'Katrín Jakobsdóttir er formaður Vinstrihreyfingarinnar - græns framboðs og forsætisráðherra Íslands.', 'Katrín Jakobsdóttir er formaður Vinstrihreyfingarinnar - græns framboðs og forsætisráðherra Íslands.', NULL, '2020-03-31 20:12:32.274453', 'Wikipedia', 'Katrín Jakobsdóttir', NULL, NULL, '123', NULL, NULL, '127.0.0.1', '{"subject": "Katrín Jakobsdóttir"}'),
('ce1957a4-72c2-11ea-99c0-820d5d3a9700', '2020-03-30 20:12:39.323793', '["hvað er sjö sinnum fimm?"]', 'hvað er sjö sinnum fimm', 'Hvað er sjö sinnum fimm?', '35', 'sjö sinnum fimm er 35', NULL, NULL, 'Arithmetic', '7 * 5', NULL, NULL, '321', NULL, NULL, '127.0.0.1', '{"result": 35}'),
('d68d909e-72c2-11ea-99c0-820d5d3a9700', '2020-03-30 20:12:53.577556', '["hvað er það deilt með fimm"]', 'hvað er það deilt með fimm', 'Hvað er það deilt með fimm?', '7', 'það deilt með fimm er 7', NULL, NULL, 'Arithmetic', '35 / 5', NULL, NULL, '321', NULL, NULL, '127.0.0.1', '{"result": 7.0}'),
('e13ea744-72c2-11ea-99c0-820d5d3a9700', '2020-03-30 20:13:11.52153', '["hvað er klukkan"]', 'hvað er klukkan', 'Hvað er klukkan?', '20:13', 'Klukkan er 20:13.', NULL, NULL, 'Time', 'Atlantic/Reykjavik', NULL, NULL, '321', NULL, NULL, '127.0.0.1', NULL),
('e13ea744-72c2-11ea-99d0-820d5d3a9700', '2020-03-31 20:13:11.52153', '["hvað er klukkan"]', 'GREYNIR_TESTING', 'Hvað er klukkan?', '20:13', 'Klukkan er 20:13.', NULL, NULL, 'Time', 'Atlantic/Reykjavik', NULL, NULL, '123456789', NULL, NULL, '127.0.0.1', NULL);

INSERT INTO querydata ("client_id", "key", "created", "modified", "data") VALUES
('123456789', 'name', '2020-09-26 21:12:56.20056', '2020-09-26 21:21:15.873656', '{"full": "Sveinbjörn Þórðarson", "first": "Sveinbjörn", "gender": "kk"}'),
('9A30D6B7-F0C9-48CF-A567-4E9E7D8997C5', 'name', '2020-09-26 22:13:11.164278', '2020-09-28 14:50:52.701844', '{"full": "Sveinbjörn Þórðarson", "first": "Sveinbjörn", "gender": "kk"}');
