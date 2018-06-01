SELECT 'LEDGER_SEQ', MAX(ledgerseq) from ledgerheaders;

SELECT 'NUM_OFFERS', COUNT(*) FROM offers;
SELECT 'NUM_ACCOUNTS_WITH_OFFERS', COUNT(*)
    FROM (SELECT DISTINCT offers.sellerid FROM offers) AS offers;

SELECT 'NUM_ACCOUNTS', COUNT(*) FROM accounts
UNION SELECT 'NUM_ACCOUNTS_WITH_EXCESS_NATIVE_SELLING_LIABILITIES', COUNT(*)
    FROM accounts
    INNER JOIN (SELECT sellerid AS accountid, SUM(amount) AS amount FROM offers WHERE sellingassettype = 0 GROUP BY sellerid) AS liabilities
    ON accounts.accountid = liabilities.accountid
    WHERE accounts.balance - (2+accounts.numsubentries) * 5000000 < liabilities.amount
UNION SELECT 'NUM_ACCOUNTS_WITH_EXCESS_NATIVE_BUYING_LIABILITIES', COUNT(*)
    FROM accounts
    INNER JOIN (SELECT sellerid AS accountid, SUM(amount * price) AS amount FROM offers WHERE buyingassettype = 0 GROUP BY sellerid) AS liabilities
    ON accounts.accountid = liabilities.accountid
    WHERE accounts.balance + liabilities.amount > 9223372036854775807;

SELECT 'NUM_OFFERS_NATIVE', COUNT(*) FROM offers WHERE sellingassettype = 0 OR buyingassettype = 0
UNION SELECT 'NUM_OFFERS_WITH_EXCESS_NATIVE_SELLING_LIABILITIES', COUNT(*)
    FROM offers
    INNER JOIN (SELECT accounts.accountid
                    FROM accounts
                    INNER JOIN (SELECT sellerid AS accountid, SUM(amount) AS amount FROM offers WHERE sellingassettype = 0 GROUP BY sellerid) AS liabilities
                    ON accounts.accountid = liabilities.accountid
                    WHERE accounts.balance - (2+accounts.numsubentries) * 5000000 < liabilities.amount) AS exceeds
    ON offers.sellerid = exceeds.accountid
UNION SELECT 'NUM_OFFERS_WITH_EXCESS_NATIVE_BUYING_LIABILITIES', COUNT(*)
    FROM offers
    INNER JOIN (SELECT accounts.accountid
                    FROM accounts
                    INNER JOIN (SELECT sellerid AS accountid, SUM(amount * price) AS amount FROM offers WHERE buyingassettype = 0 GROUP BY sellerid) AS liabilities
                    ON accounts.accountid = liabilities.accountid
                    WHERE accounts.balance + liabilities.amount > 9223372036854775807) AS exceeds
    ON offers.sellerid = exceeds.accountid;

SELECT 'NUM_ACCOUNTS', COUNT(*) FROM accounts
UNION SELECT 'NUM_ACCOUNTS_WITH_EXCESS_NONNATIVE_SELLING_LIABILITIES', COUNT(*)
    FROM (SELECT DISTINCT trustlines.accountid
            FROM trustlines
            INNER JOIN (SELECT sellerid AS accountid, sellingassetcode AS asset, sellingissuer AS issuer, SUM(amount) AS amount
                            FROM offers WHERE sellingassettype != 0 GROUP BY sellerid, sellingassetcode, sellingissuer) AS liabilities
            ON trustlines.accountid = liabilities.accountid AND trustlines.assetcode = liabilities.asset AND trustlines.issuer = liabilities.issuer
            WHERE trustlines.balance < liabilities.amount) AS trustlines
UNION SELECT 'NUM_ACCOUNTS_WITH_EXCESS_NONNATIVE_BUYING_LIABILITIES', COUNT(*)
    FROM (SELECT DISTINCT trustlines.accountid
            FROM trustlines
            INNER JOIN (SELECT sellerid AS accountid, buyingassetcode AS asset, buyingissuer AS issuer, SUM(amount * price) AS amount
                            FROM offers WHERE buyingassettype != 0 GROUP BY sellerid, buyingassetcode, buyingissuer) AS liabilities
            ON trustlines.accountid = liabilities.accountid AND trustlines.assetcode = liabilities.asset AND trustlines.issuer = liabilities.issuer
            WHERE trustlines.balance + liabilities.amount > trustlines.tlimit) AS trustlines;

SELECT 'NUM_OFFERS_NONNATIVE', COUNT(*) FROM offers WHERE sellingassettype != 0 AND buyingassettype != 0
UNION SELECT 'NUM_OFFERS_WITH_EXCESS_NONNATIVE_SELLING_LIABILITIES', COUNT(*)
    FROM offers
    INNER JOIN (SELECT trustlines.accountid, trustlines.assetcode, trustlines.issuer
                    FROM trustlines
                    INNER JOIN (SELECT sellerid AS accountid, sellingassetcode AS asset, sellingissuer AS issuer, SUM(amount) AS amount
                                    FROM offers WHERE sellingassettype != 0 GROUP BY sellerid, sellingassetcode, sellingissuer) AS liabilities
                    ON trustlines.accountid = liabilities.accountid AND trustlines.assetcode = liabilities.asset AND trustlines.issuer = liabilities.issuer
                    WHERE trustlines.balance < liabilities.amount) AS exceeds
    ON offers.sellerid = exceeds.accountid AND offers.sellingassetcode = exceeds.assetcode AND offers.sellingissuer = exceeds.issuer
UNION SELECT 'NUM_OFFERS_WITH_EXCESS_NONNATIVE_BUYING_LIABILITIES', COUNT(*)
    FROM offers
    INNER JOIN (SELECT trustlines.accountid, trustlines.assetcode, trustlines.issuer
                    FROM trustlines
                    INNER JOIN (SELECT sellerid AS accountid, buyingassetcode AS asset, buyingissuer AS issuer, SUM(amount * price) AS amount
                                    FROM offers WHERE buyingassettype != 0 GROUP BY sellerid, buyingassetcode, buyingissuer) AS liabilities
                    ON trustlines.accountid = liabilities.accountid AND trustlines.assetcode = liabilities.asset AND trustlines.issuer = liabilities.issuer
                    WHERE trustlines.balance + liabilities.amount > trustlines.tlimit) AS exceeds
    ON offers.sellerid = exceeds.accountid AND offers.buyingassetcode = exceeds.assetcode AND offers.buyingissuer = exceeds.issuer;

SELECT offers.sellerid, offers.sellingassetcode, offers.sellingissuer, offers.buyingassetcode, offers.buyingissuer
    FROM offers
    INNER JOIN (SELECT accounts.accountid
                    FROM (SELECT accountid FROM accounts WHERE GET_BYTE(DECODE(accounts.thresholds, 'base64'), 0) = 0) as accounts
                    LEFT JOIN (SELECT accountid, SUM(weight) AS weight FROM signers GROUP BY accountid) AS signers
                    ON accounts.accountid = signers.accountid
                    WHERE signers.weight IS NULL) AS locked
    ON offers.sellerid = locked.accountid;

SELECT offers.sellerid, offers.sellingassetcode, offers.sellingissuer, offers.buyingassetcode, offers.buyingissuer
    FROM offers
    INNER JOIN (SELECT accounts.accountid
                    FROM accounts
                    LEFT JOIN (SELECT accountid, SUM(weight) AS weight FROM signers GROUP BY accountid) AS signers
                    ON accounts.accountid = signers.accountid
                    WHERE COALESCE(signers.weight, 0) + GET_BYTE(DECODE(accounts.thresholds, 'base64'), 0) < GET_BYTE(DECODE(accounts.thresholds, 'base64'), 2)) AS locked
    ON offers.sellerid = locked.accountid;

