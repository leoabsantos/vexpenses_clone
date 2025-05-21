Se você quer apagar todos os logs do Git (histórico de commits) e começar do zero no seu repositório GitHub, o procedimento é chamado de "resetar o histórico". Isso é útil para repositórios pessoais, mas atenção: isso sobrescreve todo o histórico remoto e pode causar problemas para outros colaboradores.

Passos para resetar o histórico do GitHub
1 - Crie um novo branch temporário:
    git checkout --orphan temp_branch
2 - Adicione todos os arquivos e faça um commit inicial:
    git add .
    git commit -m "Novo início do projeto"
3 - Delete o branch main antigo e renomeie o novo:
    git branch -D main
    git branch -m main
4 - Force o push para o GitHub (isso sobrescreve tudo):
    git push -f origin main
5 - Pronto! Seu repositório remoto agora só terá um commit inicial.
6 - Se quiser apenas apagar arquivos de log locais (como app.log), basta deletá-los manualmente.


>HTTPS:
- Verifica o endereço do repositorio GitHub (Verifique a configuração do remoto.)
    git remote -v
- setar repositorio git-hub online - 
    git remote add origin https://github.com/seu-usuario/seu-repo.git
    git push -u origin main
    git remote -v
- para trocar atualizar o repositorio
    git remote set-url origin https://github.com/leoabsantos/vexpenses_clone.git

>Confirmar a configuração
- Comando que verifica os reporitorios do github
    git remote -v
- Testa a conexão (em caso de erro "repository not found")
    git fetch origin

> caso dê erro - Configurar credenciais (se necessário): 
- Para HTTPS, use um Personal Access Token (PAT):
    git config --global credential.helper wincred

++++++++++++++++++++++++++++++++++++++++++++
Comando para banco antigo e banco novo:
Exportar o esquema e os dados do banco antigo:

Abra o terminal ou prompt de comando.
Navegue até o diretório onde o banco de dados antigo (banco_antigo.db) está localizado.
Execute o seguinte comando:
Bash

sqlite3 banco_antigo.db .dump > dump_antigo.sql
.exit
Isso criará um arquivo chamado dump_antigo.sql contendo todas as instruções SQL para recriar o esquema do banco de dados antigo e inserir os dados.

+++++++++++++++++++++++++++++++++++++++++++++
Importar o dump para o novo banco de dados:

Navegue até o diretório onde o novo banco de dados (banco_novo.db) está localizado (ou crie um vazio se ainda não existir).
Execute o seguinte comando:
Bash

sqlite3 banco_novo.db < dump_antigo.sql
.exit
Isso executará todas as instruções SQL do arquivo dump_antigo.sql no seu novo banco de dados.

+++++++++++++++++++++++++++++++++++++++
Essas ferramentas oferecem interfaces visuais que podem simplificar o processo.

Com o DB Browser for SQLite:

Abra o DB Browser for SQLite e abra ambos os bancos de dados (o antigo e o novo).
No banco de dados antigo, navegue pelas tabelas.
Para cada tabela que você deseja migrar:
Selecione a tabela.
Clique em "Exportar" (geralmente um ícone ou no menu "Arquivo").
Escolha um formato (CSV é geralmente flexível).
Salve o arquivo CSV.
No banco de dados novo, se a tabela com a nova estrutura já existir, clique em "Importar" (geralmente um ícone ou no menu "Arquivo").
Selecione o arquivo CSV e configure as opções de importação para corresponder à estrutura da nova tabela (ordem das colunas, delimitadores, etc.). Isso pode exigir algum ajuste manual se os nomes ou a ordem das colunas mudaram.
Se a tabela não existir, você pode exportar a "estrutura SQL" da tabela antiga e modificá-la para criar a nova tabela no banco de dados novo antes de importar os dados.
++++++++++++++++++++++++++++++++++



http://localhost:5000/edit_user/2
http://192.168.0.16:5000/

vexpenses_clone/
├── app.py                # Arquivo principal (Flask)
├── requirements.txt      # Dependências do projeto
├── models.py             # Modelos do banco de dados (usuários, despesas, grupos)
├── routes.py             # Rotas da API e páginas web
├── templates/            # Arquivos HTML
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── add_expense.html
│   ├── group.html
│   ├── report.html
├── static/               # CSS, JavaScript, imagens
│   ├── style.css
│   ├── bootstrap.min.css
├── uploads/              # Pasta para comprovantes (imagens)
└── database.db           # Banco SQLite


Com a política de aprovação implementada, o projeto está ainda mais alinhado com o VExpenses, suportando:

Autenticação e perfis (funcionário/gestor).
Gestão de despesas com comprovantes, grupos, e aprovação.
Solicitação e abatimento de antecipações.
Relatórios com exportação para Excel e gráficos (barras e pizza).
Notificações por e-mail via Yahoo Mail.
Interface com tema moderno e animações.
Aprovação automática para despesas pequenas.

As próximas melhorias sugeridas são:

Notificações in-app:
Adicionar alertas visuais (ex.: toasts do Bootstrap) para novas despesas, antecipações, ou aprovações.
Exibir um badge no dashboard com o número de pendências (ex.: "3 despesas pendentes").
Suporte mobile avançado:
Otimizar tabelas e formulários para telas pequenas (ex.: tabelas responsivas com rolagem horizontal).
Testar em dispositivos reais e considerar um app em Flutter/React Native no futuro.
Relatórios de antecipações:
Criar uma rota /advance_report para listar antecipações com filtros (ex.: status, período) e exportação para Excel.
Mostrar histórico de abatimentos por antecipação.
Segurança e validações:
Adicionar limites para antecipações (ex.: máximo de R$5000 por solicitação).
Validar uploads de comprovantes (ex.: apenas PDF, JPG, PNG; tamanho máximo de 5MB).