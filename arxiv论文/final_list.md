# 自动定理证明（ATP）领域文献清单

共 **100 篇**，来源以 arXiv 为主（93 篇），辅以 7 篇高影响力经典文献（DOI）。
分类：综述 / 传统符号ATP / 神经定理证明 / 证明助手 / 证明搜索 / 基准数据集 / 应用。

## 目录结构

```
ATP_Papers/
├─ 01_Survey综述
├─ 02_Traditional_ATP传统符号自动定理证明
├─ 03_Neural_ATP神经定理证明
├─ 04_Proof_Assistant证明助手
├─ 05_Proof_Search证明搜索算法
├─ 06_Benchmark_Dataset基准数据集
├─ 07_Application应用
└─ 文献清单.md
```

## 文献总表

| 序号 | 分类 | 标题 | 作者 | 时间 | 编号/DOI | 主页 | PDF | 一句话摘要 |
|---|---|---|---|---|---|---|---|---|
| 1 | 综述类 Survey/Review | Artificial Intelligence for Mathematical Reasoning: An Integrated Survey of Language Models, Neuro-symbolic Systems, and Verified Discovery | Syed Rifat Raiyan, Mohsinul Kabir, Hasan Mahmud, Md Kamrul Hasan, Sophia Ananiadou | 2026-06-07 | arXiv:2606.08728 | [主页](https://arxiv.org/abs/2606.08728) | [PDF](https://arxiv.org/pdf/2606.08728) | 全面综述语言模型、神经符号系统与可验证发现的数学推理 AI 研究脉络。 |
| 2 | 综述类 Survey/Review | Autoformalization in the Era of Large Language Models: A Survey | Ke Weng, Lun Du, Sirui Li, Wangyue Lu, Haozhe Sun, Hengyu Liu, Tiancheng Zhang | 2025-05-29 | arXiv:2505.23486 | [主页](https://arxiv.org/abs/2505.23486) | [PDF](https://arxiv.org/pdf/2505.23486) | 系统梳理大语言模型时代自动形式化（autoformalization）的方法、挑战与评测。 |
| 3 | 综述类 Survey/Review | A Comprehensive Survey of the Lean 4 Theorem Prover: Architecture, Applications, and Advances | Xichen Tang | 2025-01-28 | arXiv:2501.18639 | [主页](https://arxiv.org/abs/2501.18639) | [PDF](https://arxiv.org/pdf/2501.18639) | 对 Lean 4 定理证明器的架构、应用与进展进行全面综述。 |
| 4 | 综述类 Survey/Review | A Survey on Mathematical Reasoning and Optimization with Large Language Models | Ali Forootani | 2025-03-22 | arXiv:2503.17726 | [主页](https://arxiv.org/abs/2503.17726) | [PDF](https://arxiv.org/pdf/2503.17726) | 综述大语言模型用于数学推理与优化问题的进展、基准与局限。 |
| 5 | 综述类 Survey/Review | A Survey on Deep Learning for Theorem Proving | Zhaoyu Li, Jialiang Sun, Logan Murphy, Qidong Su, Zenan Li, Xian Zhang, Kaiyu Yang, Xujie Si | 2024-04-15 | arXiv:2404.09939 | [主页](https://arxiv.org/abs/2404.09939) | [PDF](https://arxiv.org/pdf/2404.09939) | 系统总结深度学习（含 LLM）用于定理证明与证明搜索的代表性工作。 |
| 6 | 综述类 Survey/Review | Learning Guided Automated Reasoning: A Brief Survey | Lasse Blaauwbroek, David Cerna, Thibault Gauthier, Jan Jakubův, Cezary Kaliszyk, Martin Suda, Josef Urban | 2024-03-06 | arXiv:2403.04017 | [主页](https://arxiv.org/abs/2403.04017) | [PDF](https://arxiv.org/pdf/2403.04017) | 简要综述机器学习引导自动推理（如 ATP、SAT/SMT）的研究方向。 |
| 7 | 综述类 Survey/Review | Proof Assistants for Teaching: a Survey | Frédéric Tran Minh, Laure Gonnord, Julien Narboux | 2025-05-09 | arXiv:2505.13472 | [主页](https://arxiv.org/abs/2505.13472) | [PDF](https://arxiv.org/pdf/2505.13472) | 综述证明助手（Coq、Lean、Isabelle 等）在数学与计算机教学中的应用。 |
| 8 | 综述类 Survey/Review | A Survey on Theorem Provers in Formal Methods | M. Saqib Nawaz, Moin Malik, Yi Li, Meng Sun, M. Ikram Ullah Lali | 2019-12-06 | arXiv:1912.03028 | [主页](https://arxiv.org/abs/1912.03028) | [PDF](https://arxiv.org/pdf/1912.03028) | 综述形式化方法中各类定理证明器（交互式与自动）的原理与对比。 |
| 9 | 综述类 Survey/Review | A Survey of Languages for Formalizing Mathematics | Cezary Kaliszyk, Florian Rabe | 2020-05-26 | arXiv:2005.12876 | [主页](https://arxiv.org/abs/2005.12876) | [PDF](https://arxiv.org/pdf/2005.12876) | 综述用于形式化数学的证明语言与库（Lean、Coq、Isabelle 等）的现状。 |
| 10 | 综述类 Survey/Review | ML + FV = ♥? A Survey on the Application of Machine Learning to Formal Verification | Moussa Amrani, Levi Lúcio, Adrien Bibal | 2018-06-10 | arXiv:1806.03600 | [主页](https://arxiv.org/abs/1806.03600) | [PDF](https://arxiv.org/pdf/1806.03600) | 经典综述，梳理机器学习技术应用于形式验证与定理证明的交叉方向。 |
| 11 | 传统符号ATP Traditional ATP | Superposition for Lambda-Free Higher-Order Logic | Alexander Bentkamp, Jasmin Blanchette, Simon Cruanes, Uwe Waldmann | 2020-05-05 | arXiv:2005.02094 | [主页](https://arxiv.org/abs/2005.02094) | [PDF](https://arxiv.org/pdf/2005.02094) | 提出并实现无 λ 高阶逻辑的叠加演算，扩展一阶自动定理证明能力。 |
| 12 | 传统符号ATP Traditional ATP | Hierarchic Superposition Revisited | Peter Baumgartner, Uwe Waldmann | 2019-04-07 | arXiv:1904.03776 | [主页](https://arxiv.org/abs/1904.03776) | [PDF](https://arxiv.org/pdf/1904.03776) | 重新审视并完善层次叠加演算（hierarchic superposition）的理论与实现。 |
| 13 | 传统符号ATP Traditional ATP | Subsumption Demodulation in First-Order Theorem Proving | Bernhard Gleiss, Laura Kovacs, Jakob Rath | 2020-01-28 | arXiv:2001.10213 | [主页](https://arxiv.org/abs/2001.10213) | [PDF](https://arxiv.org/pdf/2001.10213) | 研究一阶定理证明中 subsumption demodulation 的冗余规则与完备性。 |
| 14 | 传统符号ATP Traditional ATP | The Vampire Diary | Filip Bártek, Ahmed Bhayat, Robin Coutelier, Márton Hajdu, Matthias Hetzenberger, Petra Hozzová, Laura Kovács, Jakob Rath, Michael Rawson, Giles Reger, Martin Suda, Johannes Schoisswohl, Andrei Voronkov | 2025-06-03 | arXiv:2506.03030 | [主页](https://arxiv.org/abs/2506.03030) | [PDF](https://arxiv.org/pdf/2506.03030) | Vampire 作者回顾该一阶证明器的历史演进、技术决策与工程经验。 |
| 15 | 传统符号ATP Traditional ATP | Program Synthesis in Saturation | Petra Hozzová, Laura Kovács, Chase Norman, Andrei Voronkov | 2024-02-29 | arXiv:2402.18962 | [主页](https://arxiv.org/abs/2402.18962) | [PDF](https://arxiv.org/pdf/2402.18962) | 把程序综合嵌入饱和式证明搜索，统一推理与代码生成。 |
| 16 | 传统符号ATP Traditional ATP | Rewriting and Inductive Reasoning | Márton Hajdu, Laura Kovács, Michael Rawson | 2024-02-29 | arXiv:2402.19199 | [主页](https://arxiv.org/abs/2402.19199) | [PDF](https://arxiv.org/pdf/2402.19199) | 探讨重写与归纳推理在自动证明中的结合及其完备性。 |
| 17 | 传统符号ATP Traditional ATP | Getting Saturated with Induction | Márton Hajdu, Petra Hozzová, Laura Kovács, Giles Reger, Andrei Voronkov | 2024-02-29 | arXiv:2402.18954 | [主页](https://arxiv.org/abs/2402.18954) | [PDF](https://arxiv.org/pdf/2402.18954) | 讨论在饱和循环中集成归纳推理以处理递归数据结构。 |
| 18 | 传统符号ATP Traditional ATP | Complete Trigger Selection in Satisfiability modulo first-order Theories | Christopher Lynch, Stephen Miner | 2023-06-15 | arXiv:2306.09436 | [主页](https://arxiv.org/abs/2306.09436) | [PDF](https://arxiv.org/pdf/2306.09436) | 研究 SMT 中一阶理论触发（trigger）选择的完备性判定问题。 |
| 19 | 传统符号ATP Traditional ATP | SAT-Based Subsumption Resolution | Robin Coutelier, Laura Kovács, Michael Rawson, Jakob Rath | 2024-01-31 | arXiv:2401.17832 | [主页](https://arxiv.org/abs/2401.17832) | [PDF](https://arxiv.org/pdf/2401.17832) | 用 SAT 求解加速一阶 subsumption 消解，提升叠加证明器性能。 |
| 20 | 传统符号ATP Traditional ATP | AC Simplifications and Closure Redundancies in the Superposition Calculus | André Duarte, Konstantin Korovin | 2021-07-18 | arXiv:2107.08409 | [主页](https://arxiv.org/abs/2107.08409) | [PDF](https://arxiv.org/pdf/2107.08409) | 分析叠加演算中结合交换（AC）化简与闭包冗余规则。 |
| 21 | 传统符号ATP Traditional ATP | First-Order Theorem Proving and Vampire | Laura Kovács, Andrei Voronkov | 2013 | DOI:10.1007/978-3-642-39799-8_1 | [主页](https://link.springer.com/chapter/10.1007/978-3-642-39799-8_1) | — | 经典论文，系统介绍一阶定理证明器 Vampire 的架构与关键技术。 |
| 22 | 传统符号ATP Traditional ATP | System Description: E 1.8 | Stephan Schulz | 2013 | DOI:10.1007/978-3-642-45221-5_49 | [主页](https://link.springer.com/chapter/10.1007/978-3-642-45221-5_49) | — | 经典系统描述，介绍高性能一阶自动定理证明器 E 1.8 的核心技术。 |
| 23 | 神经定理证明 Neural ATP | DeepMath - Deep Sequence Models for Premise Selection | Alex A. Alemi, Francois Chollet, Niklas Een, Geoffrey Irving, Christian Szegedy, Josef Urban | 2016-06-14 | arXiv:1606.04442 | [主页](https://arxiv.org/abs/1606.04442) | [PDF](https://arxiv.org/pdf/1606.04442) | DeepMath：用深度序列模型为高阶逻辑定理证明做前提选择（premise selection）。 |
| 24 | 神经定理证明 Neural ATP | GamePad: A Learning Environment for Theorem Proving | Daniel Huang, Prafulla Dhariwal, Dawn Song, Ilya Sutskever | 2018-06-02 | arXiv:1806.00608 | [主页](https://arxiv.org/abs/1806.00608) | [PDF](https://arxiv.org/pdf/1806.00608) | GamePad：构建定理证明的强化学习环境，用策略学习证明策略。 |
| 25 | 神经定理证明 Neural ATP | HOList: An Environment for Machine Learning of Higher-Order Theorem Proving | Kshitij Bansal, Sarah M. Loos, Markus N. Rabe, Christian Szegedy, Stewart Wilcox | 2019-04-05 | arXiv:1904.03241 | [主页](https://arxiv.org/abs/1904.03241) | [PDF](https://arxiv.org/pdf/1904.03241) | HOList：面向高阶逻辑定理证明的机器学习环境与基准。 |
| 26 | 神经定理证明 Neural ATP | Learning to Prove Theorems via Interacting with Proof Assistants | Kaiyu Yang, Jia Deng | 2019-05-21 | arXiv:1905.09381 | [主页](https://arxiv.org/abs/1905.09381) | [PDF](https://arxiv.org/pdf/1905.09381) | CoqGym：让智能体与 Coq 证明助手交互来学习证明策略与 AST 生成。 |
| 27 | 神经定理证明 Neural ATP | Learning to Prove Theorems by Learning to Generate Theorems | Mingzhe Wang, Jia Deng | 2020-02-17 | arXiv:2002.07019 | [主页](https://arxiv.org/abs/2002.07019) | [PDF](https://arxiv.org/pdf/2002.07019) | ProverBot9001：通过自举生成定理来学习证明，扩大训练数据与泛化能力。 |
| 28 | 神经定理证明 Neural ATP | Generative Language Modeling for Automated Theorem Proving | Stanislas Polu, Ilya Sutskever | 2020-09-07 | arXiv:2009.03393 | [主页](https://arxiv.org/abs/2009.03393) | [PDF](https://arxiv.org/pdf/2009.03393) | GPT-f：开创性地用生成式语言模型（GPT）直接生成 Metamath 形式化证明。 |
| 29 | 神经定理证明 Neural ATP | Proof Artifact Co-training for Theorem Proving with Language Models | Jesse Michael Han, Jason Rute, Yuhuai Wu, Edward W. Ayers, Stanislas Polu | 2021-02-11 | arXiv:2102.06203 | [主页](https://arxiv.org/abs/2102.06203) | [PDF](https://arxiv.org/pdf/2102.06203) | PACT：用证明中间产物（term、子目标）与语言模型联合训练提升证明能力。 |
| 30 | 神经定理证明 Neural ATP | Thor: Wielding Hammers to Integrate Language Models and Automated Theorem Provers | Albert Q. Jiang, Wenda Li, Szymon Tworkowski, Konrad Czechowski, Tomasz Odrzygóźdź, Piotr Miłoś, Yuhuai Wu, Mateja Jamnik | 2022-05-22 | arXiv:2205.10893 | [主页](https://arxiv.org/abs/2205.10893) | [PDF](https://arxiv.org/pdf/2205.10893) | Thor：用 Sledgehammer 选择前提并组合语言模型与自动证明器证 Isabelle 定理。 |
| 31 | 神经定理证明 Neural ATP | Autoformalization with Large Language Models | Yuhuai Wu, Albert Q. Jiang, Wenda Li, Markus N. Rabe, Charles Staats, Mateja Jamnik, Christian Szegedy | 2022-05-25 | arXiv:2205.12615 | [主页](https://arxiv.org/abs/2205.12615) | [PDF](https://arxiv.org/pdf/2205.12615) | 首次大规模研究用大语言模型把自然语言数学陈述自动形式化。 |
| 32 | 神经定理证明 Neural ATP | Draft, Sketch, and Prove: Guiding Formal Theorem Provers with Informal Proofs | Albert Q. Jiang, Sean Welleck, Jin Peng Zhou, Wenda Li, Jiacheng Liu, Mateja Jamnik, Timothée Lacroix, Yuhuai Wu, Guillaume Lample | 2022-10-21 | arXiv:2210.12283 | [主页](https://arxiv.org/abs/2210.12283) | [PDF](https://arxiv.org/pdf/2210.12283) | Draft-Sketch-Prove：用非形式化证明草稿引导 Isabelle 形式证明器。 |
| 33 | 神经定理证明 Neural ATP | Magnushammer: A Transformer-Based Approach to Premise Selection | Maciej Mikuła, Szymon Tworkowski, Szymon Antoniak, Bartosz Piotrowski, Albert Qiaochu Jiang, Jin Peng Zhou, Christian Szegedy, Łukasz Kuciński, Piotr Miłoś, Yuhuai Wu | 2023-03-08 | arXiv:2303.04488 | [主页](https://arxiv.org/abs/2303.04488) | [PDF](https://arxiv.org/pdf/2303.04488) | Magnushammer：基于 Transformer 的前提选择模型，显著超越 Sledgehammer。 |
| 34 | 神经定理证明 Neural ATP | Baldur: Whole-Proof Generation and Repair with Large Language Models | Emily First, Markus N. Rabe, Talia Ringer, Yuriy Brun | 2023-03-08 | arXiv:2303.04910 | [主页](https://arxiv.org/abs/2303.04910) | [PDF](https://arxiv.org/pdf/2303.04910) | Baldur：一次生成整段 Isabelle 证明并在失败时用 LLM 修复。 |
| 35 | 神经定理证明 Neural ATP | LeanDojo: Theorem Proving with Retrieval-Augmented Language Models | Kaiyu Yang, Aidan M. Swope, Alex Gu, Rahul Chalamala, Peiyang Song, Shixing Yu, Saad Godil, Ryan Prenger, Anima Anandkumar | 2023-06-27 | arXiv:2306.15626 | [主页](https://arxiv.org/abs/2306.15626) | [PDF](https://arxiv.org/pdf/2306.15626) | LeanDojo：面向 Lean 的检索增强证明器，含数据提取与重放基准。 |
| 36 | 神经定理证明 Neural ATP | LEGO-Prover: Neural Theorem Proving with Growing Libraries | Haiming Wang, Huajian Xin, Chuanyang Zheng, Lin Li, Zhengying Liu, Qingxing Cao, Yinya Huang, Jing Xiong, Han Shi, Enze Xie, Jian Yin, Zhenguo Li, Heng Liao, Xiaodan Liang | 2023-10-01 | arXiv:2310.00656 | [主页](https://arxiv.org/abs/2310.00656) | [PDF](https://arxiv.org/pdf/2310.00656) | LEGO-Prover：用不断增长的证明库支持神经定理证明与自举。 |
| 37 | 神经定理证明 Neural ATP | Lean Copilot: Large Language Models as Copilots for Theorem Proving in Lean | Peiyang Song, Kaiyu Yang, Anima Anandkumar | 2024-04-18 | arXiv:2404.12534 | [主页](https://arxiv.org/abs/2404.12534) | [PDF](https://arxiv.org/pdf/2404.12534) | Lean Copilot：把 LLM 作为 Lean 内嵌副驾驶，提供策略建议与证明搜索。 |
| 38 | 神经定理证明 Neural ATP | DeepSeek-Prover: Advancing Theorem Proving in LLMs through Large-Scale Synthetic Data | Huajian Xin, Daya Guo, Zhihong Shao, Zhizhou Ren, Qihao Zhu, Bo Liu, Chong Ruan, Wenda Li, Xiaodan Liang | 2024-05-23 | arXiv:2405.14333 | [主页](https://arxiv.org/abs/2405.14333) | [PDF](https://arxiv.org/pdf/2405.14333) | DeepSeek-Prover：用大规模合成数据训练 LLM 提升 Lean 4 定理证明。 |
| 39 | 神经定理证明 Neural ATP | TheoremLlama: Transforming General-Purpose LLMs into Lean4 Experts | Ruida Wang, Jipeng Zhang, Yizhen Jia, Rui Pan, Shizhe Diao, Renjie Pi, Tong Zhang | 2024-07-03 | arXiv:2407.03203 | [主页](https://arxiv.org/abs/2407.03203) | [PDF](https://arxiv.org/pdf/2407.03203) | TheoremLlama：把通用 LLM 微调为 Lean 4 证明专家。 |
| 40 | 神经定理证明 Neural ATP | Lean-STaR: Learning to Interleave Thinking and Proving | Haohan Lin, Zhiqing Sun, Sean Welleck, Yiming Yang | 2024-07-14 | arXiv:2407.10040 | [主页](https://arxiv.org/abs/2407.10040) | [PDF](https://arxiv.org/pdf/2407.10040) | Lean-STaR：让模型在证明过程中交替生成非形式化思考与形式化策略。 |
| 41 | 神经定理证明 Neural ATP | InternLM2.5-StepProver: Advancing Automated Theorem Proving via Critic-Guided Search | Zijian Wu, Suozhi Huang, Zhejian Zhou, Huaiyuan Ying, Zheng Yuan, Wenwei Zhang, Dahua Lin, Kai Chen | 2024-10-21 | arXiv:2410.15700 | [主页](https://arxiv.org/abs/2410.15700) | [PDF](https://arxiv.org/pdf/2410.15700) | InternLM2.5-StepProver：用批评者引导搜索与过程监督推进自动证明。 |
| 42 | 神经定理证明 Neural ATP | DeepSeek-Prover-V2: Advancing Formal Mathematical Reasoning via Reinforcement Learning for Subgoal Decomposition | Z. Z. Ren, Zhihong Shao, Junxiao Song, Huajian Xin, Haocheng Wang, Wanjia Zhao, Liyue Zhang, Zhe Fu, Qihao Zhu, Dejian Yang, Z. F. Wu, Zhibin Gou, Shirong Ma, Hongxuan Tang, Yuxuan Liu, Wenjun Gao, Daya Guo, Chong Ruan | 2025-04-30 | arXiv:2504.21801 | [主页](https://arxiv.org/abs/2504.21801) | [PDF](https://arxiv.org/pdf/2504.21801) | DeepSeek-Prover-V2：用强化学习做子目标分解，显著提升形式化数学推理。 |
| 43 | 证明助手工程 Proof Assistant | The Lean mathematical library | The mathlib Community | 2019-10-21 | arXiv:1910.09336 | [主页](https://arxiv.org/abs/1910.09336) | [PDF](https://arxiv.org/pdf/1910.09336) | The mathlib Community 的经典论文，介绍 Lean 数学库 mathlib 的设计与规模。 |
| 44 | 证明助手工程 Proof Assistant | Lean-auto: An Interface between Lean 4 and Automated Theorem Provers | Yicheng Qian, Joshua Clune, Clark Barrett, Jeremy Avigad | 2025-05-20 | arXiv:2505.14929 | [主页](https://arxiv.org/abs/2505.14929) | [PDF](https://arxiv.org/pdf/2505.14929) | Lean-auto：为 Lean 4 与自动定理证明器之间提供接口与互操作。 |
| 45 | 证明助手工程 Proof Assistant | Compositional pre-processing for automated reasoning in dependent type theory | Valentin Blot, Denis Cousineau, Enzo Crance, Louise Dubois de Prisque, Chantal Keller, Assia Mahboubi, Pierre Vial | 2022-04-06 | arXiv:2204.02643 | [主页](https://arxiv.org/abs/2204.02643) | [PDF](https://arxiv.org/pdf/2204.02643) | 研究依赖类型论中自动推理的组合式预处理技术。 |
| 46 | 证明助手工程 Proof Assistant | Trocq: Proof Transfer for Free, With or Without Univalence | Cyril Cohen, Enzo Crance, Assia Mahboubi | 2023-10-21 | arXiv:2310.14022 | [主页](https://arxiv.org/abs/2310.14022) | [PDF](https://arxiv.org/pdf/2310.14022) | Trocq：在等价性/单值性（univalence）下实现证明的自动迁移。 |
| 47 | 证明助手工程 Proof Assistant | ProofAug: Efficient Neural Theorem Proving via Fine-grained Proof Structure Analysis | Haoxiong Liu, Jiacheng Sun, Zhenguo Li, Andrew C Yao | 2025-01-30 | arXiv:2501.18310 | [主页](https://arxiv.org/abs/2501.18310) | [PDF](https://arxiv.org/pdf/2501.18310) | ProofAug：通过细粒度证明结构分析提升神经定理证明效率。 |
| 48 | 证明助手工程 Proof Assistant | Lean-SMT: An SMT tactic for discharging proof goals in Lean | Abdalrhman Mohamed, Tomaz Mascarenhas, Harun Khan, Haniel Barbosa, Andrew Reynolds, Yicheng Qian, Cesare Tinelli, Clark Barrett | 2025-05-21 | arXiv:2505.15796 | [主页](https://arxiv.org/abs/2505.15796) | [PDF](https://arxiv.org/pdf/2505.15796) | Lean-SMT：把 SMT 求解器集成为 Lean 的策略以自动消解目标。 |
| 49 | 证明助手工程 Proof Assistant | The Isabelle ENIGMA | Zarathustra A. Goertzel, Jan Jakubův, Cezary Kaliszyk, Miroslav Olšák, Jelle Piepenbrock, Josef Urban | 2022-05-04 | arXiv:2205.01981 | [主页](https://arxiv.org/abs/2205.01981) | [PDF](https://arxiv.org/pdf/2205.01981) | Isabelle ENIGMA：为 Isabelle 引入机器学习引导的证明搜索与前提选择。 |
| 50 | 证明助手工程 Proof Assistant | Concrete Semantics with Coq and CoqHammer | Łukasz Czajka, Burak Ekici, Cezary Kaliszyk | 2018-08-20 | arXiv:1808.06413 | [主页](https://arxiv.org/abs/1808.06413) | [PDF](https://arxiv.org/pdf/1808.06413) | Concrete Semantics 教材配套，展示 Coq 与 CoqHammer 的自动化证明实践。 |
| 51 | 证明助手工程 Proof Assistant | Tactic Learning and Proving for the Coq Proof Assistant | Lasse Blaauwbroek, Josef Urban, Herman Geuvers | 2020-03-20 | arXiv:2003.09140 | [主页](https://arxiv.org/abs/2003.09140) | [PDF](https://arxiv.org/pdf/2003.09140) | 研究 Coq 证明助手中策略（tactic）的学习与自动证明。 |
| 52 | 证明助手工程 Proof Assistant | Lemmas: Generation, Selection, Application | Michael Rawson, Christoph Wernhard, Zsolt Zombori, Wolfgang Bibel | 2023-03-10 | arXiv:2303.05854 | [主页](https://arxiv.org/abs/2303.05854) | [PDF](https://arxiv.org/pdf/2303.05854) | Lemmas：系统研究引理的生成、选择与应用以辅助证明。 |
| 53 | 证明助手工程 Proof Assistant | Reconstructing veriT Proofs in Isabelle/HOL | Mathias Fleury, Hans-Jörg Schurr | 2019-08-26 | arXiv:1908.09480 | [主页](https://arxiv.org/abs/1908.09480) | [PDF](https://arxiv.org/pdf/1908.09480) | 把 veriT 证明在 Isabelle/HOL 中重建，打通 SMT 与交互证明器。 |
| 54 | 证明助手工程 Proof Assistant | When Agda met Vampire | Artjoms Šinkarovs, Michael Rawson | 2026-02-21 | arXiv:2602.18844 | [主页](https://arxiv.org/abs/2602.18844) | [PDF](https://arxiv.org/pdf/2602.18844) | When Agda met Vampire：连接 Agda 依赖类型证明与一阶证明器 Vampire。 |
| 55 | 证明助手工程 Proof Assistant | The Network Structure of Mathlib | Xinze Li, Nanyun Peng, Simone Severini, Patrick Shafto | 2026-04-26 | arXiv:2604.24797 | [主页](https://arxiv.org/abs/2604.24797) | [PDF](https://arxiv.org/pdf/2604.24797) | 分析 mathlib 数学库的依赖网络结构，揭示形式化知识组织规律。 |
| 56 | 证明助手工程 Proof Assistant | CSLib: The Lean Computer Science Library | Clark Barrett, Swarat Chaudhuri, Fabrizio Montesi, Jim Grundy, Pushmeet Kohli, Leonardo de Moura, Alexandre Rademaker, Sorrachai Yingchareonthawornchai | 2026-02-04 | arXiv:2602.04846 | [主页](https://arxiv.org/abs/2602.04846) | [PDF](https://arxiv.org/pdf/2602.04846) | CSLib：面向计算机科学的 Lean 证明库，提供基础定理与自动化。 |
| 57 | 证明助手工程 Proof Assistant | LeanSearch v2: Global Premise Retrieval for Lean 4 Theorem Proving | Guoxiong Gao, Zeming Sun, Jiedong Jiang, Yutong Wang, Jingda Xu, Peihao Wu, Bryan Dai, Bin Dong | 2026-05-13 | arXiv:2605.13137 | [主页](https://arxiv.org/abs/2605.13137) | [PDF](https://arxiv.org/pdf/2605.13137) | LeanSearch v2：面向 Lean 4 的全局前提检索与证明搜索系统。 |
| 58 | 证明助手工程 Proof Assistant | The Fundamental Theorem of Asset Pricing, Formalized in Lean 4 | Raphael Coelho | 2026-06-27 | arXiv:2606.28990 | [主页](https://arxiv.org/abs/2606.28990) | [PDF](https://arxiv.org/pdf/2606.28990) | 在 Lean 4 中形式化金融数学的资产定价基本定理（FTAP）。 |
| 59 | 证明助手工程 Proof Assistant | Formalizing Automated Market Makers in the Lean 4 Theorem Prover | Daniele Pusceddu, Massimo Bartoletti | 2024-02-08 | arXiv:2402.06064 | [主页](https://arxiv.org/abs/2402.06064) | [PDF](https://arxiv.org/pdf/2402.06064) | 在 Lean 4 中形式化自动做市商（AMM），验证去中心化金融机制性质。 |
| 60 | 证明助手工程 Proof Assistant | A formal proof of the Ramanujan--Nagell theorem in Lean 4 | Barinder S. Banwait | 2026-04-10 | arXiv:2604.09808 | [主页](https://arxiv.org/abs/2604.09808) | [PDF](https://arxiv.org/pdf/2604.09808) | 在 Lean 4 中给出 Ramanujan–Nagell 定理的完整形式化证明。 |
| 61 | 证明助手工程 Proof Assistant | The Lean 4 Theorem Prover and Programming Language | Leonardo de Moura, Sebastian Ullrich | 2021 | DOI:10.1007/978-3-030-79876-5_37 | [主页](https://lean-lang.org/papers/lean4.pdf) | [PDF](https://lean-lang.org/papers/lean4.pdf) | Lean 4 的官方论文，介绍其兼具定理证明与编程能力的依赖类型系统。 |
| 62 | 证明助手工程 Proof Assistant | Isabelle/HOL: A Proof Assistant for Higher-Order Logic | Tobias Nipkow, Lawrence C. Paulson, Markus Wenzel | 2002 | DOI:10.1007/3-540-45949-9 | [主页](https://isabelle.in.tum.de/dist/Isabelle2023/doc/tutorial.pdf) | — | 经典教程书，系统介绍高阶逻辑证明助手 Isabelle/HOL 的原理与使用。 |
| 63 | 搜索/规划算法 Proof Search | Deep Network Guided Proof Search | Sarah Loos, Geoffrey Irving, Christian Szegedy, Cezary Kaliszyk | 2017-01-24 | arXiv:1701.06972 | [主页](https://arxiv.org/abs/1701.06972) | [PDF](https://arxiv.org/pdf/1701.06972) | Deep Network Guided Proof Search：用深度网络引导一阶证明搜索（loop 终止选择）。 |
| 64 | 搜索/规划算法 Proof Search | HyperTree Proof Search for Neural Theorem Proving | Guillaume Lample, Marie-Anne Lachaux, Thibaut Lavril, Xavier Martinet, Amaury Hayat, Gabriel Ebner, Aurélien Rodriguez, Timothée Lacroix | 2022-05-23 | arXiv:2205.11491 | [主页](https://arxiv.org/abs/2205.11491) | [PDF](https://arxiv.org/pdf/2205.11491) | HyperTree Proof Search：训练策略与价值网络并用超树搜索解决证明问题。 |
| 65 | 搜索/规划算法 Proof Search | BFS-Prover: Scalable Best-First Tree Search for LLM-based Automatic Theorem Proving | Ran Xin, Chenguang Xi, Jie Yang, Feng Chen, Hang Wu, Xia Xiao, Yifan Sun, Shen Zheng, Kai Shen | 2025-02-05 | arXiv:2502.03438 | [主页](https://arxiv.org/abs/2502.03438) | [PDF](https://arxiv.org/pdf/2502.03438) | BFS-Prover：可扩展的最佳优先树搜索框架，用于 LLM 自动定理证明。 |
| 66 | 搜索/规划算法 Proof Search | Automated Theorem Proving in Intuitionistic Propositional Logic by Deep Reinforcement Learning | Mitsuru Kusumoto, Keisuke Yahata, Masahiro Sakai | 2018-11-02 | arXiv:1811.00796 | [主页](https://arxiv.org/abs/1811.00796) | [PDF](https://arxiv.org/pdf/1811.00796) | 用深度强化学习在直觉主义命题逻辑中做自动证明搜索。 |
| 67 | 搜索/规划算法 Proof Search | Reinforcement Learning of Theorem Proving | Cezary Kaliszyk, Josef Urban, Henryk Michalewski, Mirek Olšák | 2018-05-19 | arXiv:1805.07563 | [主页](https://arxiv.org/abs/1805.07563) | [PDF](https://arxiv.org/pdf/1805.07563) | Reinforcement Learning of Theorem Proving：把证明建模为 RL 决策过程。 |
| 68 | 搜索/规划算法 Proof Search | Learning to Guide a Saturation-Based Theorem Prover | Ibrahim Abdelaziz, Maxwell Crouse, Bassem Makni, Vernon Austil, Cristina Cornelio, Shajith Ikbal, Pavan Kapanipathi, Ndivhuwo Makondo, Kavitha Srinivas, Michael Witbrock, Achille Fokoue | 2021-06-07 | arXiv:2106.03906 | [主页](https://arxiv.org/abs/2106.03906) | [PDF](https://arxiv.org/pdf/2106.03906) | Learning to Guide a Saturation-Based Theorem Prover：用学习引导饱和证明器。 |
| 69 | 搜索/规划算法 Proof Search | A Deep Reinforcement Learning Approach to First-Order Logic Theorem Proving | Maxwell Crouse, Ibrahim Abdelaziz, Bassem Makni, Spencer Whitehead, Cristina Cornelio, Pavan Kapanipathi, Kavitha Srinivas, Veronika Thost, Michael Witbrock, Achille Fokoue | 2019-11-05 | arXiv:1911.02065 | [主页](https://arxiv.org/abs/1911.02065) | [PDF](https://arxiv.org/pdf/1911.02065) | 用深度强化学习为一阶逻辑定理证明做证明步骤搜索。 |
| 70 | 搜索/规划算法 Proof Search | Prolog Technology Reinforcement Learning Prover | Zsolt Zombori, Josef Urban, Chad E. Brown | 2020-04-15 | arXiv:2004.06997 | [主页](https://arxiv.org/abs/2004.06997) | [PDF](https://arxiv.org/pdf/2004.06997) | Prolog Technology RL Prover：把 Prolog 技术与强化学习结合做证明。 |
| 71 | 搜索/规划算法 Proof Search | Machine Learning Guidance and Proof Certification for Connection Tableaux | Michael Färber, Cezary Kaliszyk, Josef Urban | 2018-05-08 | arXiv:1805.03107 | [主页](https://arxiv.org/abs/1805.03107) | [PDF](https://arxiv.org/pdf/1805.03107) | 用机器学习引导连接表（connection tableaux）证明与证明证书生成。 |
| 72 | 搜索/规划算法 Proof Search | Proving Theorems Recursively | Haiming Wang, Huajian Xin, Zhengying Liu, Wenda Li, Yinya Huang, Jianqiao Lu, Zhicheng Yang, Jing Tang, Jian Yin, Zhenguo Li, Xiaodan Liang | 2024-05-23 | arXiv:2405.14414 | [主页](https://arxiv.org/abs/2405.14414) | [PDF](https://arxiv.org/pdf/2405.14414) | Proving Theorems Recursively：用递归分解方法逐步构造形式证明。 |
| 73 | 搜索/规划算法 Proof Search | Learning Formal Mathematics From Intrinsic Motivation | Gabriel Poesia, David Broman, Nick Haber, Noah D. Goodman | 2024-06-30 | arXiv:2407.00695 | [主页](https://arxiv.org/abs/2407.00695) | [PDF](https://arxiv.org/pdf/2407.00695) | 从内在动机出发学习形式化数学，自动生成目标与证明探索。 |
| 74 | 搜索/规划算法 Proof Search | Bourbaki: Self-Generated and Goal-Conditioned MDPs for Theorem Proving | Matthieu Zimmer, Xiaotong Ji, Rasul Tutunov, Anthony Bordg, Jun Wang, Haitham Bou Ammar | 2025-07-03 | arXiv:2507.02726 | [主页](https://arxiv.org/abs/2507.02726) | [PDF](https://arxiv.org/pdf/2507.02726) | Bourbaki：用自生成的目标条件 MDP 框架驱动定理证明探索。 |
| 75 | 基准与数据集 Benchmark/Dataset | MiniF2F: a cross-system benchmark for formal Olympiad-level mathematics | Kunhao Zheng, Jesse Michael Han, Stanislas Polu | 2021-08-31 | arXiv:2109.00110 | [主页](https://arxiv.org/abs/2109.00110) | [PDF](https://arxiv.org/pdf/2109.00110) | MiniF2F：跨系统（Lean/Isabelle/Metamath）的奥赛级形式化数学基准。 |
| 76 | 基准与数据集 Benchmark/Dataset | ProofNet: Autoformalizing and Formally Proving Undergraduate-Level Mathematics | Zhangir Azerbayev, Bartosz Piotrowski, Hailey Schoelkopf, Edward W. Ayers, Dragomir Radev, Jeremy Avigad | 2023-02-24 | arXiv:2302.12433 | [主页](https://arxiv.org/abs/2302.12433) | [PDF](https://arxiv.org/pdf/2302.12433) | ProofNet：本科级数学的自动形式化与形式证明联合基准。 |
| 77 | 基准与数据集 Benchmark/Dataset | FIMO: A Challenge Formal Dataset for Automated Theorem Proving | Chengwu Liu, Jianhao Shen, Huajian Xin, Zhengying Liu, Ye Yuan, Haiming Wang, Wei Ju, Chuanyang Zheng, Yichun Yin, Lin Li, Ming Zhang, Qun Liu | 2023-09-08 | arXiv:2309.04295 | [主页](https://arxiv.org/abs/2309.04295) | [PDF](https://arxiv.org/pdf/2309.04295) | FIMO：面向自动定理证明的形式化 IMO 挑战数据集。 |
| 78 | 基准与数据集 Benchmark/Dataset | NaturalProofs: Mathematical Theorem Proving in Natural Language | Sean Welleck, Jiacheng Liu, Ronan Le Bras, Hannaneh Hajishirzi, Yejin Choi, Kyunghyun Cho | 2021-03-24 | arXiv:2104.01112 | [主页](https://arxiv.org/abs/2104.01112) | [PDF](https://arxiv.org/pdf/2104.01112) | NaturalProofs：自然语言数学定理证明的数据集与检索基线。 |
| 79 | 基准与数据集 Benchmark/Dataset | Reliable Evaluation and Benchmarks for Statement Autoformalization | Auguste Poiroux, Gail Weiss, Viktor Kunčak, Antoine Bosselut | 2024-06-11 | arXiv:2406.07222 | [主页](https://arxiv.org/abs/2406.07222) | [PDF](https://arxiv.org/pdf/2406.07222) | 为陈述自动形式化（statement autoformalization）提供可靠评测与基准。 |
| 80 | 基准与数据集 Benchmark/Dataset | FormalMATH: Benchmarking Formal Mathematical Reasoning of Large Language Models | Zhouliang Yu, Ruotian Peng, Keyi Ding, Yizhe Li, Zhongyuan Peng, Minghao Liu, Yifan Zhang, Zheng Yuan, Huajian Xin, Wenhao Huang, Yandong Wen, Ge Zhang, Weiyang Liu | 2025-05-05 | arXiv:2505.02735 | [主页](https://arxiv.org/abs/2505.02735) | [PDF](https://arxiv.org/pdf/2505.02735) | FormalMATH：面向 LLM 形式化数学推理的跨系统评测基准。 |
| 81 | 基准与数据集 Benchmark/Dataset | Multilingual Mathematical Autoformalization | Albert Q. Jiang, Wenda Li, Mateja Jamnik | 2023-11-07 | arXiv:2311.03755 | [主页](https://arxiv.org/abs/2311.03755) | [PDF](https://arxiv.org/pdf/2311.03755) | Multilingual Mathematical Autoformalization：多语言数学陈述自动形式化基准。 |
| 82 | 基准与数据集 Benchmark/Dataset | Neural Theorem Proving for Verification Conditions: A Real-World Benchmark | Qiyuan Xu, Xiaokun Luan, Renxi Wang, Joshua Ong Jun Leang, Peixin Wang, Haonan Li, Wenda Li, Conrad Watt | 2026-01-26 | arXiv:2601.18944 | [主页](https://arxiv.org/abs/2601.18944) | [PDF](https://arxiv.org/pdf/2601.18944) | 面向验证条件（verification conditions）的神经定理证明真实场景基准。 |
| 83 | 基准与数据集 Benchmark/Dataset | TheoremBench: Evaluating LLMs on Theorem Proving in Formal Mathematics | QuocViet Pham, Elvir Karimov, Andrey Galichin, Ivan Oseledets | 2026-06-08 | arXiv:2606.09450 | [主页](https://arxiv.org/abs/2606.09450) | [PDF](https://arxiv.org/pdf/2606.09450) | TheoremBench：在形式化数学上系统评测 LLM 定理证明能力的基准。 |
| 84 | 基准与数据集 Benchmark/Dataset | MathAtlas: A Benchmark for Autoformalization in the Wild | Nilay Patel, Noah Arias, Davit Babayan, Victoria Cochran, Timothy Libman, Hafsah Mahmood, Liam McCarty, Soli Munoz, Laurel Willey, Jeffrey Flanigan | 2026-05-13 | arXiv:2605.14061 | [主页](https://arxiv.org/abs/2605.14061) | [PDF](https://arxiv.org/pdf/2605.14061) | MathAtlas：面向真实场景（in the wild）自动形式化的基准。 |
| 85 | 基准与数据集 Benchmark/Dataset | TaoBench: Do Automated Theorem Prover LLMs Generalize Beyond MathLib? | Alexander K Taylor, Junyi Zhang, Ethan Ji, Vigyan Sahai, Haikang Deng, Yuanzhou Chen, Yifan Yuan, Di Wu, Jia-Chen Gu, Kai-Wei Chang, Nanyun Peng, Amit Sahai, Wei Wang | 2026-03-13 | arXiv:2603.12744 | [主页](https://arxiv.org/abs/2603.12744) | [PDF](https://arxiv.org/pdf/2603.12744) | TaoBench：检验自动证明 LLM 是否泛化到 mathlib 之外的定理。 |
| 86 | 基准与数据集 Benchmark/Dataset | The TPTP Problem Library and Associated Infrastructure | Geoff Sutcliffe | 2017 | DOI:10.1007/s10817-017-9407-7 | [主页](http://www.tptp.org/) | — | 经典论文，介绍 ATP 领域标准问题库 TPTP 及其基础设施。 |
| 87 | 应用类 Application | Trustworthy Verification of RISC-V Binaries Using Symbolic Execution in HolBA | Karl Palmskog, Andreas Lindner, Scott Constable, Roberto Guanciale, Hamed Nemati | 2025-03-18 | arXiv:2503.14135 | [主页](https://arxiv.org/abs/2503.14135) | [PDF](https://arxiv.org/pdf/2503.14135) | 用 HolBA 中的符号执行对 RISC-V 二进制做可信验证。 |
| 88 | 应用类 Application | Formal Verification of the Sumcheck Protocol | Azucena Garvía Bosshard, Jonathan Bootle, Christoph Sprenger | 2024-02-08 | arXiv:2402.06093 | [主页](https://arxiv.org/abs/2402.06093) | [PDF](https://arxiv.org/pdf/2402.06093) | 在证明助手中形式化验证密码学中的 sumcheck 协议。 |
| 89 | 应用类 Application | Selene: Pioneering Automated Proof in Software Verification | Lichen Zhang, Shuai Lu, Nan Duan | 2024-01-15 | arXiv:2401.07663 | [主页](https://arxiv.org/abs/2401.07663) | [PDF](https://arxiv.org/pdf/2401.07663) | Selene：在软件验证中引入自动化证明的端到端系统。 |
| 90 | 应用类 Application | Accelerating Verified-Compiler Development with a Verified Rewriting Engine | Jason Gross, Andres Erbsen, Jade Philipoom, Rajashree Agrawal, Adam Chlipala | 2022-05-02 | arXiv:2205.00862 | [主页](https://arxiv.org/abs/2205.00862) | [PDF](https://arxiv.org/pdf/2205.00862) | 用经验证的改写引擎加速验证编译器的开发。 |
| 91 | 应用类 Application | Improving Counterexample Quality from Failed Program Verification | Li Huang, Bertrand Meyer, Manuel Oriol | 2022-08-21 | arXiv:2208.10492 | [主页](https://arxiv.org/abs/2208.10492) | [PDF](https://arxiv.org/pdf/2208.10492) | 改进程序验证失败时反例的质量与可读性。 |
| 92 | 应用类 Application | QCP: A Practical Separation Logic-based C Program Verification Tool | Xiwei Wu, Yueyang Feng, Xiaoyang Lu, Tianchuan Lin, Kan Liu, Zhiyi Wang, Shushu Wu, Lihan Xie, Chengxi Yang, Hongyi Zhong, Zihan Zhang, Juanru Li, Naijun Zhan, Zhenjiang Hu, Qinxiang Cao | 2025-05-19 | arXiv:2505.12878 | [主页](https://arxiv.org/abs/2505.12878) | [PDF](https://arxiv.org/pdf/2505.12878) | QCP：基于分离逻辑的实用 C 程序验证工具。 |
| 93 | 应用类 Application | Towards Real-World Industrial-Scale Verification: LLM-Driven Theorem Proving on seL4 | Jianyu Zhang, Fuyuan Zhang, Jiayi Lu, Jilin Hu, Xiaoyi Yin, Long Zhang, Feng Yang, Yongwang Zhao | 2026-02-09 | arXiv:2602.08384 | [主页](https://arxiv.org/abs/2602.08384) | [PDF](https://arxiv.org/pdf/2602.08384) | 用 LLM 驱动定理证明，把形式验证扩展到 seL4 等工业级系统。 |
| 94 | 应用类 Application | RAG-Verus: Repository-Level Program Verification with LLMs using Retrieval Augmented Generation | Sicheng Zhong, Jiading Zhu, Yifang Tian, Xujie Si | 2025-02-07 | arXiv:2502.05344 | [主页](https://arxiv.org/abs/2502.05344) | [PDF](https://arxiv.org/pdf/2502.05344) | RAG-Verus：用检索增强生成做仓库级 Rust 程序验证。 |
| 95 | 应用类 Application | Towards an Automatic Proof of Lamport's Paxos | Aman Goel, Karem A. Sakallah | 2021-08-19 | arXiv:2108.08796 | [主页](https://arxiv.org/abs/2108.08796) | [PDF](https://arxiv.org/pdf/2108.08796) | 尝试自动证明分布式共识算法 Lamport Paxos 的正确性。 |
| 96 | 应用类 Application | Verified VCG and Verified Compiler for Dafny | Daniel Nezamabadi, Magnus O. Myreen, Yong Kiam Tan | 2025-12-04 | arXiv:2512.05262 | [主页](https://arxiv.org/abs/2512.05262) | [PDF](https://arxiv.org/pdf/2512.05262) | 为 Dafny 构建验证 VC 生成器与经验证的编译器。 |
| 97 | 应用类 Application | Verified Correctness and Security of mbedTLS HMAC-DRBG | Katherine Q. Ye, Matthew Green, Naphat Sanguansin, Lennart Beringer, Adam Petcher, Andrew W. Appel | 2017-08-28 | arXiv:1708.08542 | [主页](https://arxiv.org/abs/1708.08542) | [PDF](https://arxiv.org/pdf/1708.08542) | 验证 mbedTLS 中 HMAC-DRBG 密码模块的正确性与安全性。 |
| 98 | 应用类 Application | Formal Verification of Physical Layer Security Protocols for Next-Generation Communication Networks (extended version) | Kangfeng Ye, Roberto Metere, Jim Woodcock, Poonam Yadav | 2025-08-26 | arXiv:2508.19430 | [主页](https://arxiv.org/abs/2508.19430) | [PDF](https://arxiv.org/pdf/2508.19430) | 形式化验证下一代通信网络的物理层安全协议。 |
| 99 | 应用类 Application | seL4: Formal Verification of an OS Kernel | Gerwin Klein et al. | 2009 | DOI:10.1145/1629575.1629596 | [主页](https://dl.acm.org/doi/10.1145/1629575.1629596) | [PDF](https://www.sigops.org/s/conferences/sosp/2009/papers/klein-sosp09.pdf) | 里程碑工作，首次完成通用操作系统微内核 seL4 的端到端形式化验证。 |
| 100 | 应用类 Application | Formal Verification of a Realistic Compiler | Xavier Leroy | 2009 | DOI:10.1145/1538788.1538814 | [主页](https://xavierleroy.org/publi/compcert-CACM.pdf) | [PDF](https://xavierleroy.org/publi/compcert-CACM.pdf) | 里程碑工作，介绍经验证的真实编译器 CompCert 及其正确性保证。 |

## 批量下载 PDF 链接（可直接整段复制）

https://arxiv.org/pdf/2606.08728
https://arxiv.org/pdf/2505.23486
https://arxiv.org/pdf/2501.18639
https://arxiv.org/pdf/2503.17726
https://arxiv.org/pdf/2404.09939
https://arxiv.org/pdf/2403.04017
https://arxiv.org/pdf/2505.13472
https://arxiv.org/pdf/1912.03028
https://arxiv.org/pdf/2005.12876
https://arxiv.org/pdf/1806.03600
https://arxiv.org/pdf/2005.02094
https://arxiv.org/pdf/1904.03776
https://arxiv.org/pdf/2001.10213
https://arxiv.org/pdf/2506.03030
https://arxiv.org/pdf/2402.18962
https://arxiv.org/pdf/2402.19199
https://arxiv.org/pdf/2402.18954
https://arxiv.org/pdf/2306.09436
https://arxiv.org/pdf/2401.17832
https://arxiv.org/pdf/2107.08409
https://arxiv.org/pdf/1606.04442
https://arxiv.org/pdf/1806.00608
https://arxiv.org/pdf/1904.03241
https://arxiv.org/pdf/1905.09381
https://arxiv.org/pdf/2002.07019
https://arxiv.org/pdf/2009.03393
https://arxiv.org/pdf/2102.06203
https://arxiv.org/pdf/2205.10893
https://arxiv.org/pdf/2205.12615
https://arxiv.org/pdf/2210.12283
https://arxiv.org/pdf/2303.04488
https://arxiv.org/pdf/2303.04910
https://arxiv.org/pdf/2306.15626
https://arxiv.org/pdf/2310.00656
https://arxiv.org/pdf/2404.12534
https://arxiv.org/pdf/2405.14333
https://arxiv.org/pdf/2407.03203
https://arxiv.org/pdf/2407.10040
https://arxiv.org/pdf/2410.15700
https://arxiv.org/pdf/2504.21801
https://arxiv.org/pdf/1910.09336
https://arxiv.org/pdf/2505.14929
https://arxiv.org/pdf/2204.02643
https://arxiv.org/pdf/2310.14022
https://arxiv.org/pdf/2501.18310
https://arxiv.org/pdf/2505.15796
https://arxiv.org/pdf/2205.01981
https://arxiv.org/pdf/1808.06413
https://arxiv.org/pdf/2003.09140
https://arxiv.org/pdf/2303.05854
https://arxiv.org/pdf/1908.09480
https://arxiv.org/pdf/2602.18844
https://arxiv.org/pdf/2604.24797
https://arxiv.org/pdf/2602.04846
https://arxiv.org/pdf/2605.13137
https://arxiv.org/pdf/2606.28990
https://arxiv.org/pdf/2402.06064
https://arxiv.org/pdf/2604.09808
https://lean-lang.org/papers/lean4.pdf
https://arxiv.org/pdf/1701.06972
https://arxiv.org/pdf/2205.11491
https://arxiv.org/pdf/2502.03438
https://arxiv.org/pdf/1811.00796
https://arxiv.org/pdf/1805.07563
https://arxiv.org/pdf/2106.03906
https://arxiv.org/pdf/1911.02065
https://arxiv.org/pdf/2004.06997
https://arxiv.org/pdf/1805.03107
https://arxiv.org/pdf/2405.14414
https://arxiv.org/pdf/2407.00695
https://arxiv.org/pdf/2507.02726
https://arxiv.org/pdf/2109.00110
https://arxiv.org/pdf/2302.12433
https://arxiv.org/pdf/2309.04295
https://arxiv.org/pdf/2104.01112
https://arxiv.org/pdf/2406.07222
https://arxiv.org/pdf/2505.02735
https://arxiv.org/pdf/2311.03755
https://arxiv.org/pdf/2601.18944
https://arxiv.org/pdf/2606.09450
https://arxiv.org/pdf/2605.14061
https://arxiv.org/pdf/2603.12744
https://arxiv.org/pdf/2503.14135
https://arxiv.org/pdf/2402.06093
https://arxiv.org/pdf/2401.07663
https://arxiv.org/pdf/2205.00862
https://arxiv.org/pdf/2208.10492
https://arxiv.org/pdf/2505.12878
https://arxiv.org/pdf/2602.08384
https://arxiv.org/pdf/2502.05344
https://arxiv.org/pdf/2108.08796
https://arxiv.org/pdf/2512.05262
https://arxiv.org/pdf/1708.08542
https://arxiv.org/pdf/2508.19430
https://www.sigops.org/s/conferences/sosp/2009/papers/klein-sosp09.pdf
https://xavierleroy.org/publi/compcert-CACM.pdf
