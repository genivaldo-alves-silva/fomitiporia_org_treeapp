
- Construção de árvore multiloci?
- Balões de explicação das ferramentas;
- Possibilidade dos usuários alimentarem o sistema com matrizes atualizadas com qualificação certificada?
    - Vincular a algo como treebase (com submissão auditável)/dataverse (com doi) onde podem ir subindo as matrizes alinhadas e atualizadas?
    - Vincular ao dataset maker que está sendo construído?

- Dar a opção de arquivos de amostra para o usuário testar qualquer opção do app;
- Disponibilizar um parágrafo em inglês de como citar a reconstrução de filogenia usando o fluxo do app;
- Dar mais liberdade de escolha nas análises. Veja 'https://www.genome.jp/tools/ete/';

- Não mostrar botões de download quando não houver dados por fazer download;
- Largura ser proporcional ao tamanho dos tips e ramos, tal como a altura.

- Failed jobs should free the queue
    - Testar com matriz não alinhada no modo 1 e ver comportamento do sistema
    - Pensar sobre o implementar o retry. Existe um chat iniciado com isso ('Comportamento do app em caso de falhas de job').
    - Implementar testes de arquivos por modo e retorar msg específica para o user, como o caso da matriz não alinhada usando o modo 1. Cada modo pode ter seus testes de arquivos

- Melhorar o quadro de visualização da árvore. Adicionar a opção de mover a árvore quando zoom out/in. Adicionar a opção de redimencionamento do quadro de visualização.

- Verificar o pt-br e ENG do corpo do email.

- Tratar a exceção como 'Panus sp. eciosus' ao lidar com sp. e italização;

- Dar a opção de download da árvore como imagem (ex.: PNG);

- Verificar a trimagem

- Adicionar sugestões para usar Fasttree antes de tudo, quando não se conhece o comportamento da topologia e sugestões de como usar o outgroup para enraizamento;

- Incluir no bolding as palavras 'type region', 'genus type', etc

- Verificar como está o idioma para a escrita dos emails

- Retirar o debugging deeper no log. Os endereços de emails estão sendo expostos. Há alguma conversa aqui no chat que pode ajudar. Se não me engano tem uma forma de desligar hardcoded.

- Toy datasets to teach

## Verificar

