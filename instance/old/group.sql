BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "group" (
	"id"	INTEGER NOT NULL,
	"name"	VARCHAR(100) NOT NULL,
	"creator_id"	INTEGER NOT NULL,
	PRIMARY KEY("id"),
	FOREIGN KEY("creator_id") REFERENCES "user"("id")
);
INSERT INTO "group" VALUES (1,'Comercial',1);
INSERT INTO "group" VALUES (2,'Produção',1);
INSERT INTO "group" VALUES (3,'RH',1);
INSERT INTO "group" VALUES (4,'Projeto',1);
INSERT INTO "group" VALUES (5,'Orçamento',1);
INSERT INTO "group" VALUES (6,'Administrativo',1);
INSERT INTO "group" VALUES (7,'Gerencia',1);
INSERT INTO "group" VALUES (8,'Diretoria',1);
INSERT INTO "group" VALUES (9,'Marcenaria',1);
INSERT INTO "group" VALUES (10,'Limpeza',1);
INSERT INTO "group" VALUES (11,'Montagem',1);
INSERT INTO "group" VALUES (12,'Programação Visual',1);
INSERT INTO "group" VALUES (13,'Serralheria',1);
INSERT INTO "group" VALUES (14,'Marketing',1);
COMMIT;
