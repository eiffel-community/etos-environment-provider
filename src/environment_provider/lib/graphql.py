# Copyright Axis Communications AB.
#
# For a full list of individual contributors, please see the commit history.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""GraphQL request handler module."""
from typing import Iterator, Optional

from etos_lib import ETOS


def request(etos: ETOS, query: str) -> Iterator[dict]:
    """Request graphql in a generator.

    :param etos: ETOS library instance.
    :param query: Query to send to graphql.
    :return: Iterator
    """
    wait_generator = etos.utils.wait(etos.graphql.execute, query=query)
    yield from wait_generator


def request_tercc(etos: ETOS, suite_id: str) -> Optional[dict]:
    """Request a test execution recipe collection created event from graphql.

    :param etos: ETOS library instance.
    :param suite_id: ID of execution recipe to request.
    :return: Response from graphql or None
    """
    query = """
{
  testExecutionRecipeCollectionCreated(search: "{'meta.id': '%s'}") {
    edges {
      node {
        data {
          batchesUri
          customData {
            key
            value
          }
        }
        meta {
          id
        }
        links {
          ... on Cause {
            links {
              __typename
              ... on ArtifactCreated {
                data {
                  identity
                }
                meta {
                  id
                }
              }
            }
          }
        }
      }
    }
  }
}
    """
    for response in request(etos, query % suite_id):
        if response:
            return response
    return None


def request_artifact_created(etos: ETOS, artifact_id: str) -> Optional[dict]:
    """Request an artifact created event from graphql.

    :param etos: ETOS library instance.
    :param artifact_id: ID of artifact to request.
    :return: Response from graphql or None
    """
    query = """
{
  artifactCreated(search: "{'meta.id': '%s'}") {
    edges {
      node {
        data {
          identity
        }
      }
    }
  }
}
    """
    for response in request(etos, query % artifact_id):
        if response:
            return response
    return None


def request_activity_triggered(etos: ETOS, suite_id: str) -> Optional[dict]:
    """Request an activiy triggered event from graphql.

    :param etos: ETOS library instance.
    :param suite_id: ID of execution recipe the activity triggered links to.
    :return: Response from graphql or None
    """
    query = """
{
  activityTriggered(last: 1, search: "{'links.type': 'CAUSE', 'links.target': '%s'}") {
    edges {
      node {
        meta {
          id
        }
      }
    }
  }
}
    """
    for response in request(etos, query % suite_id):
        if response:
            return response
    return None


def request_artifact_published(etos: ETOS, artifact_id: str) -> Optional[dict]:
    """Request an artifact published event from graphql.

    :param etos: ETOS library instance.
    :type etos: :obj:`etos_lib.etos.Etos`
    :param artifact_id: ID of artifact created the artifact published links to.
    :type artifact_id: str
    :return: Response from graphql or None
    :rtype: dict or None
    """
    query = """
{
  artifactPublished(last: 1, search: "{'links.type': 'ARTIFACT', 'links.target': '%s'}") {
    edges {
      node {
        data {
          locations {
            type
            uri
          }
        }
      }
    }
  }
}
    """
    for response in request(etos, query % artifact_id):
        if response:
            return response
    return None


def request_main_suite(etos: ETOS, main_suite_id: str) -> Optional[dict]:
    """Request a test suite started event from graphql.

    :param etos: ETOS library instance.
    :param main_suite_id: ID of main suite to get from ER.
    :return: Response from graphql or None
    """
    query = """
{
  testSuiteStarted(last: 1, search: "{'meta.id': '%s'}") {
    edges {
      node {
        meta {
          id
        }
      }
    }
  }
}
    """
    for response in request(etos, query % main_suite_id):
        if response:
            try:
                _, test_suite_started = next(
                    etos.graphql.search_for_nodes(response, "testSuiteStarted")
                )
            except StopIteration:
                return None
            return test_suite_started
    return None
