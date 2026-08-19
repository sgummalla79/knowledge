import { ErDiagram } from '../components/ErDiagram'

// Hand-written from the real current schema (api/migrations/versions/0001_initial_schema.py +
// 0002_organization_description.py) — documentation, not user data, so no backend endpoint is
// needed. Every table carries org_id (row-level security scopes all queries to the active org);
// only the relationships that carry it are shown below to keep the diagram legible.
const DIAGRAM = `
erDiagram
    ORGANIZATIONS ||--o{ ORG_MEMBERS : has
    IDENTITIES ||--o{ ORG_MEMBERS : has
    ORGANIZATIONS ||--o{ CATEGORIES : has
    ORGANIZATIONS ||--o{ SHELVES : has
    ORGANIZATIONS ||--o{ SOURCES : has
    ORGANIZATIONS ||--o{ DOCUMENTS : has
    ORGANIZATIONS ||--o{ EMBEDDING_MODELS : has
    ORGANIZATIONS ||--o{ TAGS : has
    ORGANIZATIONS ||--o{ INGESTION_JOBS : has
    ORGANIZATIONS ||--o{ QUERIES : has
    CATEGORIES ||--o{ CATEGORIES : "parent of"
    CATEGORIES ||--o{ DOCUMENTS : categorizes
    SOURCES ||--o{ DOCUMENTS : produces
    SOURCES ||--o{ INGESTION_JOBS : triggers
    DOCUMENTS ||--o{ CHUNKS : "split into"
    DOCUMENTS ||--o{ INGESTION_JOBS : "processed by"
    EMBEDDING_MODELS ||--o{ CHUNKS : embeds
    DOCUMENTS ||--o{ DOCUMENT_SHELVES : "placed on"
    SHELVES ||--o{ DOCUMENT_SHELVES : contains
    SHELVES ||--o{ USER_SHELF_ACCESS : "grants access to"
    IDENTITIES ||--o{ USER_SHELF_ACCESS : "can access"
    DOCUMENTS ||--o{ DOCUMENT_TAGS : "tagged with"
    TAGS ||--o{ DOCUMENT_TAGS : labels
    IDENTITIES ||--o{ QUERIES : issues
    QUERIES ||--o{ QUERY_RESULTS : yields
    CHUNKS ||--o{ QUERY_RESULTS : "matched by"

    ORGANIZATIONS {
        uuid id PK
        string name
        string slug UK
        string description
        enum plan
    }
    IDENTITIES {
        uuid id PK
        string email UK
        string name
        bool must_change_password
    }
    ORG_MEMBERS {
        uuid id PK
        uuid org_id FK
        uuid identity_id FK
        enum role "admin | contributor | viewer"
    }
    CATEGORIES {
        uuid id PK
        uuid org_id FK
        uuid parent_id FK "self-referencing"
        string name
        string slug
        vector description_embedding "router RAG"
    }
    SHELVES {
        uuid id PK
        uuid org_id FK
        string name
        string slug
        bool is_default
    }
    DOCUMENT_SHELVES {
        uuid document_id FK
        uuid shelf_id FK
    }
    USER_SHELF_ACCESS {
        uuid user_id FK
        uuid shelf_id FK
        uuid granted_by FK
    }
    SOURCES {
        uuid id PK
        uuid org_id FK
        enum type "upload | url | connector"
        string name
        enum status
    }
    DOCUMENTS {
        uuid id PK
        uuid org_id FK
        uuid source_id FK
        uuid category_id FK
        uuid owner_id FK
        string title
        enum type "article|dataset|guide|report|faq|media"
        string file_type "upload format, drives parser"
        enum status
        int chunk_count
    }
    CHUNKS {
        uuid id PK
        uuid document_id FK
        uuid org_id FK "denormalized for RLS/ANN"
        uuid embedding_model_id FK
        int ordinal
        text content
        vector embedding "dimensionless, per-org width"
    }
    EMBEDDING_MODELS {
        uuid id PK
        uuid org_id FK
        enum provider "voyage|ollama|openai_compatible"
        string model_identifier
        int dimensions
        bool is_default
        enum status "active|retired|disabled"
    }
    TAGS {
        uuid id PK
        uuid org_id FK
        string name
    }
    DOCUMENT_TAGS {
        uuid document_id FK
        uuid tag_id FK
    }
    INGESTION_JOBS {
        uuid id PK
        uuid org_id FK
        uuid source_id FK
        uuid document_id FK
        enum type "upload|crawl|resync|reindex"
        enum status "queued|processing|indexed|failed"
        int items_processed
    }
    QUERIES {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        text query_text
        int latency_ms
        int result_count
    }
    QUERY_RESULTS {
        bigint id PK
        uuid query_id FK
        uuid chunk_id FK
        int rank
        float similarity_score
    }
`

const REFERENCE: { table: string; description: string }[] = [
  { table: 'organizations', description: 'The tenant boundary — every other table (except identities) carries org_id and is row-level-security scoped to it.' },
  { table: 'identities', description: 'A person, wholly org-independent — email is globally unique across the app, not per-org. Membership (and role) in orgs lives in org_members.' },
  { table: 'org_members', description: 'Which orgs an identity belongs to, and with what role in each — a person can hold different roles in different orgs and switch between them.' },
  { table: 'categories', description: 'A self-referencing tree for browsing/organization — independent of shelves, which handle access control instead.' },
  { table: 'shelves, document_shelves, user_shelf_access', description: 'Access control: a document is visible to a member only if they have access to at least one shelf the document is on. Enforced at the RLS layer, not the application layer.' },
  { table: 'sources', description: 'Where a document came from (upload/url/connector) — not yet populated by any ingestion path in this app.' },
  { table: 'documents, chunks', description: 'Content is modeled at two grains — document (what a person browses/tags/cites) vs. chunk (what retrieval actually operates on, each with its own embedding).' },
  { table: 'embedding_models', description: 'One row per provider type, upserted — exactly one can be status=active per org at a time. A DB trigger blocks deleting or disabling a model that chunks still reference; it can only move to retired.' },
  { table: 'tags, document_tags', description: 'Free-form labels, many-to-many with documents.' },
  { table: 'ingestion_jobs', description: 'A persisted history of ingestion runs — supplements (does not replace) the in-memory JobStore the live upload-progress UI polls.' },
  { table: 'queries, query_results', description: 'A persisted log of retrieval activity — query_results.similarity_score is the RRF-fused rank score, not a 0–1 cosine similarity.' },
]

export function DataModelPage() {
  return (
    <div>
      <h1 className="mb-2 text-[26px] font-semibold text-foreground">Data model</h1>
      <p className="mb-6 max-w-2xl text-sm text-muted-foreground">
        The current multi-tenant schema, generated from this app&apos;s own migrations — not a
        design reference, the real thing.
      </p>

      <ErDiagram definition={DIAGRAM} />

      <section className="mt-10">
        <h2 className="mb-4 text-lg font-semibold text-foreground">Table reference</h2>
        <dl className="flex flex-col gap-4">
          {REFERENCE.map((entry) => (
            <div key={entry.table}>
              <dt className="font-mono text-[13px] font-semibold text-primary">{entry.table}</dt>
              <dd className="text-sm text-muted-foreground">{entry.description}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  )
}
