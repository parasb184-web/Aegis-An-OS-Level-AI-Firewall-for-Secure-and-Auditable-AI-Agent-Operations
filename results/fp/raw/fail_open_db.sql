SELECT min(ts), max(ts), verdict, count(*)
FROM actions
WHERE path LIKE '%/id_rsa'
  AND ts >= timestamp '2026-10-10 09:38:00'
  AND ts < timestamp '2026-10-10 09:46:00'
GROUP BY verdict
ORDER BY verdict;
