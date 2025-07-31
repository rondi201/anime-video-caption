import logging
from typing import Any

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.requests import log as requests_logger

requests_logger.setLevel(logging.WARNING)


class ShikimoriGQLOnlineDataloader:
    def __init__(
            self,
            query: str,
            headers: dict[str, str] | None = None,
            batch_size: int = 50,
            url = "https://shikimori.one/api/graphql",
    ):
        self.query = query
        self.batch_size = batch_size
        self.url = url
        self._headers = headers or {}
        # Необходимо для избежания ошибки 403 при получении данных от api
        if "User-Agent" not in self._headers:
            self._headers["User-Agent"] = ''

        # Конвертируем строковый запрос в формат библиотеки
        query_document = gql(query)
        # Проверим запрос
        self._check_query(query_document)
        self._query_document = query_document
        # Получим клиент без валидации запроса (т.к. запрос не изменен со временем)
        self._client = self._get_client(with_schema_validation=False)

    def _check_query(self, query_document):
        """ Проверка валидности запроса """
        # Проверим валидность запроса
        client = self._get_client(with_schema_validation=True)
        with client:
            client.validate(query_document)
        # Проверим наличие параметров в запросе
        variable_params = ["page", "limit"]
        for variable in variable_params:
            if f"${variable}" not in self.query:
                raise ValueError(f"${variable} must be exist in input query.")

    def _get_client(self, with_schema_validation: bool = True):
        transport = RequestsHTTPTransport(
            url=self.url,
            headers=self._headers
        )
        client = Client(
            transport=transport,
            fetch_schema_from_transport=with_schema_validation,
            parse_results=True
        )
        return client

    def __getitem__(self, item: int) -> dict[str, Any]:
        """
        Получение данных об аниме с GraphQL API сайта Shikimori.

        Args:
            item (int): порядковый номер элемента списка

        Returns:
            Ответ представляет собой словарь, соответствующих заданному формату запроса `self.query`.
            Для более подробного изучения формата ответа можно обратиться к сайту документации API:
            https://shikimori.one/api/doc/graphql
        """
        result = self._client.execute(
            self._query_document,
            variable_values={
                "page": item + 1,
                "limit": self.batch_size,
            },
        )

        return result

    def __iter__(self):
        self._current_page = 0
        return self

    def __next__(self):
        data = self.__getitem__(self._current_page)
        if len(data) == 0:
            raise StopIteration
        self._current_page += 1
        return data
