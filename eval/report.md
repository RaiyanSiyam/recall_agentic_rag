# Red-Team Security Evaluation Report

Comprehensive security evaluation across **110 red-team test cases** comparing defense capabilities with guardrails **Strict vs Off**.

## Executive Security Summary

- **Overall Attack Success Rate (Strict)**: **0.0%** (Target: < 5%)
- **Attack Success Rate Without Guardrails (Off)**: **100.0%**
- **False Positive Rate on Benign Queries**: **0.0%** (Zero False Positives)
- **Pipeline Latency Overhead**: **-1.06 ms**
- **Quality Gate Status**: ✅ PASSED

## Threat Category Breakdown

| Threat Category | ASR (Guardrails OFF) | ASR (Guardrails STRICT) | Security Delta |
|:---|:---:|:---:|:---:|
| **Prompt Injection** | 100.0% | **0.0%** | -100.0% (Defended) |
| **Indirect Prompt Injection** | 100.0% | **0.0%** | -100.0% (Defended) |
| **Secret Exfiltration** | 100.0% | **0.0%** | -100.0% (Defended) |
| **Canary Leak** | 100.0% | **0.0%** | -100.0% (Defended) |
| **Destructive Actions** | 100.0% | **0.0%** | -100.0% (Defended) |
| **Memory Poisoning** | 100.0% | **0.0%** | -100.0% (Defended) |
| **Overall Attack Success Rate** | **100.0%** | **0.0%** | **-100.0% Defense Gain** |
| **Benign Query False Positive Rate** | **0.0%** | **0.0%** | **0.0% Clean Usability** |

## Mode Comparison

| Guardrail Mode | Overall ASR | Benign FPR | Avg Latency | Active Protections |
|:---|:---:|:---:|:---:|:---|
| **Strict** | **0.0%** | **0.0%** | 0.99 ms | All 10 defense stages, canary scan, propose-only actions, strict Luhn redaction |
| **Balanced** | **2.17%** | **0.0%** | 1.05 ms | Relaxed prompt suspicion, redaction active, propose-only actions active |
| **Off** | **100.0%** | **0.0%** | 2.05 ms | Baseline unshielded execution (attack demonstration mode) |

## Quality Gate Verification

✅ All 8 security gates passed successfully.
