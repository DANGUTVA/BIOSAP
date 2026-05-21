SELECT
  CardCode,
  CardName,
  SUM(DocTotal) AS TotalSales,
  COUNT(DocEntry) AS Orders
FROM OINV
GROUP BY CardCode, CardName;
