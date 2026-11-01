-- Food Rescue API: script de criação do banco (SQLite)

CREATE TABLE usuarios (
	id INTEGER NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	senha_hash VARCHAR(255) NOT NULL, 
	papel VARCHAR(20) NOT NULL, 
	criado_em DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_usuarios_email ON usuarios (email);

CREATE TABLE doadores (
	id INTEGER NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	endereco VARCHAR(255), 
	latitude FLOAT NOT NULL, 
	longitude FLOAT NOT NULL, 
	criado_em DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (usuario_id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);


CREATE TABLE instituicoes (
	id INTEGER NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	capacidade_kg FLOAT NOT NULL, 
	latitude FLOAT NOT NULL, 
	longitude FLOAT NOT NULL, 
	webhook_url VARCHAR(500), 
	ativa BOOLEAN NOT NULL, 
	criado_em DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_instituicao_capacidade CHECK (capacidade_kg > 0), 
	UNIQUE (usuario_id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);


CREATE TABLE lotes_excedentes (
	id INTEGER NOT NULL, 
	doador_id INTEGER NOT NULL, 
	descricao VARCHAR(255) NOT NULL, 
	categoria VARCHAR(40) NOT NULL, 
	quantidade_kg FLOAT NOT NULL, 
	disponivel_ate DATETIME NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	criado_em DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_lote_quantidade CHECK (quantidade_kg > 0), 
	FOREIGN KEY(doador_id) REFERENCES doadores (id) ON DELETE CASCADE
);

CREATE INDEX ix_lotes_excedentes_status ON lotes_excedentes (status);
CREATE INDEX ix_lotes_excedentes_doador_id ON lotes_excedentes (doador_id);

CREATE TABLE resgates (
	id INTEGER NOT NULL, 
	lote_id INTEGER NOT NULL, 
	instituicao_id INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	nota FLOAT NOT NULL, 
	webhook_status VARCHAR(20) NOT NULL, 
	criado_em DATETIME NOT NULL, 
	atualizado_em DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_resgate_lote_instituicao UNIQUE (lote_id, instituicao_id), 
	FOREIGN KEY(lote_id) REFERENCES lotes_excedentes (id) ON DELETE CASCADE, 
	FOREIGN KEY(instituicao_id) REFERENCES instituicoes (id) ON DELETE CASCADE
);

CREATE INDEX ix_resgates_status ON resgates (status);
CREATE INDEX ix_resgates_instituicao_id ON resgates (instituicao_id);
CREATE INDEX ix_resgates_lote_id ON resgates (lote_id);

