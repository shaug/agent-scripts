# Record webhook receipt time

Our webhook audit needs to show when an event first reached the service. Record
`received_at` for a newly received event before processing it.

Retries are normal. Delivering the same provider event ID more than once must
continue to return the stored result without applying the event or sending its
notification again. Preserve the existing provider event ID as the idempotency
key. This ticket does not change retry policy or notification content.
