## Preamble

```
SEP: 00xx
Title: XDR Base64 Encoding
Author: Leigh McCulloch <@leighmcculloch>
Status: Draft
Created: 2019-12-04
Updated: 2019-12-04
Version: 1.0.0
```

## Simple Summary

XDR messages such as transaction envelopes, transaction results, and others are often encoded into base64 as required by other SEPs or has become common and best practice to make the binary messages portable, embeddable in other message formats such as JSON.

Base64 encoders are available in the standard libraries of many programming languages and are relatively consistent. Base64 decoders are just as available but are less consistent. Some languages contain very strict base64 decoders about aspects such as padding, and others less strict. As an example, base64 that has had its padding removed will be parseable in JavaScript, Java, and Ruby, but will error in Python and Go. Because of this it is important that when base64 encoding XDR messages that they are consistently encoded according to the specification below and unaltered. Following the specification below should be low effort because many programming langauges standard libraries support this form of encoding by default, and this specification serve to capture current expectations.

## Specification

XDR messages when base64 encoded should be encoded following the specification in [RFC4648 Section 4].

The alphabet to use for encoding is the standard alphabet utilizing the `A-Z` `a-z` `0-9` `+` `/` character set for value encoding, and `=` for padding.

Special characters in the alphabet should not substituted for alternative alphabets such as the URL or Filename Safe Alphabet described in the RFCs Section 5.

Padding must always be used, and never removed from the message.

Line feeds should not be added to the base64-encoded data.

## Example

Encoding XDR messages as base64 can be done consistently in the following languages. This is not an exhaustive list and just examples.

### Go
```go
import "encoding/base64"

base64.StdEncoding.EncodeToString(xdrBytes)
```

### Java
```java
import java.util.Base64;

Base64.getEncoder().encodeToString(xdrBytes)
```

### Python
```python
import base64

base64.b64encode(xdr_bytes)
```

[RFC4648 Section 4]: https://tools.ietf.org/html/rfc4648#section-4
