# IT Terms for AI/IT Conversations

## Categorized Terms (by Similarity)

### Network and API
- API: a defined way for software systems to communicate
- MCP: Model Context Protocol, a standard way for AI models to connect to external tools and data sources
- endpoint: a specific API URL you call to perform an action
- request: data sent from a client to a server
- response: data returned by a server to a client
- payload: the main data body sent in a request or response
- HTTP: web protocol for request-response communication
- HTTPS: encrypted HTTP for secure communication
- REST: resource-oriented API style over HTTP methods
- GraphQL: query language/API runtime for flexible client data fetching
- gRPC: high-performance RPC framework often using Protocol Buffers
- WebSocket: persistent two-way communication channel over a single connection
- webhook: HTTP callback triggered by an event
- CORS: browser security policy controlling cross-origin requests
- middleware: reusable request/response processing layer
- protocol: agreed rules for communication between systems
- gateway: entry point managing traffic/auth/policies for services
- reverse proxy: server forwarding client requests to backend services
- DNS: system translating domain names to IP addresses
- CDN: globally distributed network for fast content delivery

### Data and Formats
- schema: a structured definition of data fields and types
- JSON: a lightweight text format for structured data exchange
- YAML: a human-readable configuration/data format
- XML: a markup format used to structure and exchange data
- serialization: converting data structures into storable/transmittable format
- deserialization: converting stored/transmitted format back into objects
- parsing: analyzing text/data into a structured format
- data validation: checking data meets expected rules
- data integrity: correctness and consistency of stored data
- sanitization: cleaning input to remove harmful/invalid content
- index: data structure that speeds up queries
- query: request for data from a database
- SQL: language for querying and managing relational databases
- NoSQL: non-relational database approaches for specific scalability/use needs

### Databases and Data Engineering
- transaction: group of operations treated as a single unit
- ACID: transaction properties for reliable relational operations
- normalization: organizing relational data to reduce redundancy
- denormalization: adding redundancy to improve read performance
- replication: maintaining copies of data across systems
- sharding: splitting data across partitions for scale
- consistency: guarantees about seeing the latest data state
- eventual consistency: replicas converge over time, not instantly
- ETL: Extract, Transform, Load data processing workflow
- data pipeline: automated flow for moving/transforming data
- ORM: Object-Relational Mapping layer between code and SQL database

### AI and ML
- prompt: the instruction/input given to an AI model
- system prompt: high-priority instruction that sets model behavior
- token: a small unit of text used by language models
- context window: maximum amount of text an AI model can consider at once
- inference: the process of generating output from a trained model
- hallucination: when an AI confidently generates incorrect information
- grounding: anchoring model output to trusted sources or data
- embedding: a numeric vector representation of text or objects
- vector: an ordered list of numbers representing features
- vector database: a database optimized for similarity search on vectors
- similarity search: finding items most semantically close to a query
- cosine similarity: a metric that compares angle between vectors
- retrieval: fetching relevant information before generating an answer
- RAG: Retrieval-Augmented Generation using external context during response generation
- fine-tuning: additional training on specific data to specialize a model
- checkpoint: a saved snapshot of model weights during training
- hyperparameter: a training setting chosen before model training
- learning rate: how quickly model weights are updated during training
- overfitting: when a model memorizes training data and generalizes poorly
- underfitting: when a model fails to learn patterns adequately
- benchmark: a standard test used to compare performance
- evaluation: measuring system/model quality using defined metrics

### Software Architecture and Design
- abstraction: hiding complexity behind a simpler interface
- encapsulation: bundling data and behavior with controlled access
- modularity: organizing software into independent interchangeable components
- cohesion: how closely related responsibilities are within a module
- coupling: degree of dependency between modules
- interface: contract defining available operations/behavior
- implementation: concrete code that fulfills an interface
- design pattern: reusable solution template for common design problems
- anti-pattern: common but ineffective/harmful approach
- singleton: design pattern ensuring single instance exists
- extensibility: ease of adding new features without major rewrites
- interoperability: ability of systems to work together

### Backend and Distributed Systems
- stateful: system that keeps session/state between requests
- stateless: system where each request is independent
- session: temporary user-specific interaction state
- load balancing: distributing traffic across multiple instances
- failover: automatic switch to backup component on failure
- graceful degradation: reduced functionality instead of total failure
- fallback: alternative behavior when primary path fails
- redundancy: duplicate components to increase reliability
- queue: ordered structure for pending tasks/messages
- worker: process/thread that consumes and executes queued jobs
- scheduler: component that triggers tasks by time/rules
- cron: time-based job scheduling format/system
- event-driven: architecture centered on producing/consuming events
- message broker: system routing messages between producers/consumers
- pub/sub: publish-subscribe messaging pattern
- stream processing: continuous processing of real-time data streams
- batch processing: processing data in scheduled grouped chunks

### Performance and Reliability
- latency: time taken to complete a request
- throughput: amount of work completed per unit time
- scalability: ability to handle growth in workload/users
- reliability: consistency of correct operation over time
- availability: percentage of time a service is operational
- fault tolerance: ability to continue operating despite failures
- resilience: ability to recover quickly from disruptions
- robustness: ability to perform well under varied/noisy conditions
- bottleneck: component limiting overall system performance
- timeout: maximum wait time before an operation is aborted
- retry: attempting an operation again after failure
- backoff: increasing delay between retries to reduce load
- circuit breaker: pattern that stops repeated failing calls temporarily
- rate limit: cap on request volume in a time window
- throttling: deliberately slowing request processing
- quota: allowed usage amount over a period
- caching: storing frequently used data for faster access
- cache hit: request served from cache
- cache miss: request not found in cache, requires fresh fetch
- invalidation: removing stale cache entries
- idempotent: safe to repeat an operation without changing final result

### Security
- authentication: verifying identity
- authorization: verifying permissions after identity is known
- credential: secret data used for authentication
- access control: rules determining who can access what
- IAM: Identity and Access Management policies and tooling
- encryption: transforming data to protect confidentiality
- decryption: restoring encrypted data to readable form
- hashing: one-way transformation used for integrity and lookup
- salting: adding random data before hashing to improve security
- key rotation: regularly replacing cryptographic keys
- least privilege: granting only minimal required permissions
- vulnerability: weakness that can be exploited
- exploit: method/code that uses a vulnerability
- patch: update that fixes a bug or security issue
- hardening: reducing attack surface through secure configuration
- sandbox: isolated environment for running untrusted code
- secret: sensitive config value (API key, password, token)

### DevOps, Cloud, and Deployment
- container: lightweight packaged runtime with dependencies
- image: immutable template used to create containers
- Dockerfile: instructions to build a container image
- orchestration: automated management of many containers/services
- Kubernetes: platform for container orchestration
- pod: smallest deployable compute unit in Kubernetes
- node: machine that runs workloads in a cluster
- cluster: group of machines managed as one system
- deployment: process/object for releasing app versions
- rolling update: gradual replacement of old instances with new ones
- rollback: reverting to a previously working version
- blue-green deployment: switching traffic between two production environments
- canary release: releasing to a small subset before full rollout
- feature flag: toggle that enables/disables features without redeploy
- CI: Continuous Integration with frequent automated build/test
- CD: Continuous Delivery/Deployment for automated releases
- pipeline: ordered automated steps for build/test/deploy
- build: process of compiling/packaging source code
- artifact: output package produced by a build
- staging: pre-production environment for realistic testing
- production: live environment used by real users

### Testing and Quality
- unit test: test of small isolated code behavior
- integration test: test of interactions between components
- end-to-end test: test of full workflow from user perspective
- regression test: test ensuring old functionality still works after changes
- test coverage: proportion of code executed by tests
- mock: simulated dependency used in tests
- stub: simple controlled replacement returning fixed responses
- fixture: predefined data/setup used by tests
- linting: static checks for style/errors in source code
- formatting: automated code style normalization
- static analysis: examining code without executing it
- type checking: verifying value types to catch errors early
- debugging: finding and fixing defects in code/system behavior
- profiling: measuring resource usage to locate bottlenecks
- optimization: improving performance, cost, or efficiency

### Programming Basics
- function: reusable block of code performing a specific task
- parameter: an input value passed to a function or API call
- argument: the actual value supplied to a function parameter
- immutable: data/object that cannot be changed after creation
- mutable: data/object that can be modified after creation
- compiler: tool translating source code to executable form
- interpreter: runtime executing source code directly
- runtime: environment where code executes
- exception: runtime event indicating abnormal condition
- stack trace: call history shown when an error occurs
- memory leak: unreleased memory causing growth over time
- deadlock: processes blocked waiting on each other indefinitely
- race condition: behavior depends on timing/order of concurrent operations
- concurrency: managing multiple tasks that progress over overlapping time
- parallelism: executing multiple tasks at the same time
- async: non-blocking execution model for waiting operations
- blocking: operation that prevents further progress until completion
- non-blocking: operation allowing other work while waiting

### Product, Process, and Team
- requirement: condition the system must satisfy
- spec: precise description of requirements/behavior
- acceptance criteria: testable conditions for feature completion
- use case: real scenario describing how a user achieves a goal
- user story: short statement of user need and value
- scope: defined boundaries of what is included in work
- trade-off: balancing competing priorities (speed, cost, quality)
- prioritize: rank tasks by impact, urgency, or dependency
- backlog: prioritized list of pending work
- sprint: fixed iteration period in agile development
- roadmap: planned sequence of product/technical milestones
- stakeholder: person/group affected by project outcomes
- alignment: shared understanding of goals and priorities
- incident: unplanned disruption degrading service quality
- root cause analysis: process to find fundamental cause of an issue
- postmortem: written analysis after an incident with actions
- runbook: operational instructions for common procedures/incidents
- triage: prioritizing and diagnosing incoming issues quickly
- mitigation: an action taken to reduce the impact or likelihood of a risk or problem

### Useful Conversation Verbs for AI Agents
- specify: state requirements/instructions precisely
- clarify: remove ambiguity by making intent explicit
- validate: confirm that something meets expected criteria
- verify: check correctness against specification
- align: bring understanding, scope, or implementation into agreement
- prioritize: rank tasks by impact, urgency, or dependency
- unblock: remove dependency preventing progress
- iterate: improve through repeated cycles
- converge: move toward a stable, agreed, final solution
- orchestrate: coordinate multiple services/tasks in a managed workflow
- refactor: code restructuring without changing behavior
- migrate: move data/code from one version/system to another
- deprecate: mark a feature as discouraged before removal

### Describing Design Complexity
- sophisticated: highly advanced and well-designed. Example: "This service has a sophisticated architecture with strong fault tolerance."
- elaborate: very detailed and multi-step in structure or process. Example: "The deployment pipeline is elaborate but easy to audit."
- intricate: complex with many small, interconnected parts. Example: "The parser uses intricate rules to handle edge cases."
- delicate: requiring careful handling because small changes can break behavior. Example: "This legacy integration is delicate, so we test every minor change."
