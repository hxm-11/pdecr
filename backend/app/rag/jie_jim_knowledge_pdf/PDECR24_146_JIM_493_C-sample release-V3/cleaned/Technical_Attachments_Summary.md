# Technical Attachments Summary 技术附件汇总

## 零部件状态说明 — JIM 493 C样件状态

![](../ocr/images/11ca86595ff6f4725bf7ba340bb017f6bc50e49e1dc6b3dd5011b0b52afd1c0c.jpg)

---

## 焊接和测量说明 — JIM 493 C样件状态

![](../ocr/images/6c5955dcc4615e27a0651933bb93e0af5f5be02be94cca4d4ca878200882d759.jpg)

- 将来量产采用模具件，机器人焊接工艺更稳定，此轮耐久可以覆盖将来量产状态
- 基于以往项目经验，弗吉亚手工焊接有较丰富经验，前期手工焊接件台架耐久未出现焊缝失效，此轮整车耐久风险较低
- 由于量产工装检具未及时到位，此次OTS期望用手工焊接+部分机器人焊接支持整车耐久

![](../ocr/images/31efefc6a793ef1b8d2f424ed26f8de6dd9dcbba7224e4a8db2297655fbb94bb.jpg)

---

## DOC端锥变更FEA评估 — JIM 493 C样件状态

- 1阶模态频率170.12Hz（变更前为169.2Hz）

### 应力对比

| 工况 | 变更前 | 变更后 |
|---|---|---|
| 应力 @ 150Hz (X向) | 42.3 MPa | 41 MPa |
| 应力 @ 150Hz (X向，另一测点) | 34.5 MPa | 32.7 MPa |

### 图片附件

![](../ocr/images/076628467f47a90d1c04e69c1127be8765c693d82d3c42ae5daa2b8cad34162a.jpg)

![](../ocr/images/f5f6e55748177ea918d4c81d0df73c4170e6d3677712c7aca98b9ef304a12f0a.jpg)

![](../ocr/images/77fba19f12bd4e0185114e268e9272d90ac63285549df80931a0f33540c5d4ec.jpg)

![](../ocr/images/4ae1fd6bf6adb1e4fa5ec823cb89b580958d922d1f999738007036a3ea29c7d3.jpg)

![](../ocr/images/70cf7b7e1de0ad7893ce1648296b54ff639d5e766d0460b3152fc1e8429e8532.jpg)

![](../ocr/images/e77f33dbce537d8a5b6f1c4fd53d16c8c33768bcbc2ebe5b395ccd343fe3a4b1.jpg)

![](../ocr/images/23659e76f683a188d0b467795d3df5c8c5cfcbfd3660c1b219e9e329d2223994.jpg)

![](../ocr/images/244cf118cd20a52c637a31e24f5e398263c14b1ab1f2e6d0f5b76a1b1a534392.jpg)

![](../ocr/images/eb4cc28c437e89b3fef1127cb88067b0d046916dcf4531f360cff9a60d9983b0.jpg)

---

## 吊钩反力分析 (Hook Reaction Force)

| Hook Responsibility | RB Hooks | | Customer Hooks | | | | |
|---|---|---|---|---|---|---|---|
| Point | 1 | 2 | 3 | 4 | 5 | 6 | |
| Reaction force [N] - Z | 16.4 | 39.9 | 12.8 | 19.1 | 35.7 | 13.0 | OK |
| Displacement [mm] | 1.23 | 3.00 | 0.96 | 1.43 | 2.68 | 0.97 | OK |

### 吊钩模态节点分析

| Hook location | | Conclusion |
|---|---|---|
| Model | Hook#1, Hook#2, Hook#3, Hook#4, Hook#5, Hook#6 | 经分析，吊钩位置分布较合理；另外，SCR出气端锥处有1处适合布置吊钩的位置 |
| Modal nodes (20~150Hz) | Hook#1: Modes 3,8; Hook#2: Modes 1,2,3; Hook#3: Modes 5,7,8; Hook#4: Modes 4,11; Hook#5: Modes 5,7; Hook#6: Modes 1,2,7 | |

### 图片附件

![](../ocr/images/f4071bbf804ebb926749397c02a0a4c1a2caa1ee59f890297a210e7ab807b70f.jpg)

![](../ocr/images/d63340c31dddb2f9e905e75dcc4bc17d8beca62f8fb74e905904207bef6da0ee.jpg)

![](../ocr/images/fa3ae21a0d64a4518230914898476cf997b8635d515229c1a16a7f7cb30a66a1.jpg)

---

## 模态分析 (Modal Analysis)

| Mode | Freq. (Hz) | 振型描述 | Mode | Freq. (Hz) | 振型描述 |
|---|---|---|---|---|---|
| 1 | 9.6 | Y向摆动 | 10 | 43.0 | X向一阶扭摆 |
| 2 | 10.2 | X向摆动 | 11 | 53.8 | Z向三阶扭摆 |
| 3 | 13.1 | Y向一阶扭摆 | 12 | 77.9 | Z向四阶扭摆+前吊钩局部模态 |
| 4 | 14.0 | Z向弯曲 | 13 | 82.8 | 波纹管局部模态 |
| 5 | 16.4 | Z向一阶扭摆 | 14 | 84.6 | 波纹管局部模态 |
| 6 | 19.2 | Y向弯曲 | 15 | 108.7 | 前吊钩局部模态 |
| 7 | 20.6 | Z向弯曲+尾管局部模态 | 16 | 123.9 | 波纹管局部模态 |
| 8 | 34.2 | Z向二阶扭摆 | 17 | 124.5 | SCR前吊钩+波纹管局部模态 |
| 9 | 35.7 | Y向二阶扭摆 | 18 | 125.6 | SCR前吊钩+波纹管局部模态 |

### 发动机信息

| 参数 | 值 |
|---|---|
| Engine | 4 cylinders |
| Idle | 750±50 rpm |
| 2nd order frequency | 25.5±1.7 Hz |

### 图片附件

![](../ocr/images/9c68b7b7a592275f2ac5deb62384e9fd09c8c272f5105236f1b19c5321db94e2.jpg)

![](../ocr/images/4165634bcbd9d653ec0e0ff57610f7b21a1c90581b86f83ea8aaac3a61a732de.jpg)

![](../ocr/images/3aa4180be022c1724bf66fd3950d7599fe295664229dfb4dbbf524ee3b3a6cb9.jpg)

---

## PEEQ (等效塑性应变) 分析

### 吊钩应变结果1

| | PEEQ |
|---|---|
| Step 2 | 1.39% |
| Step 4 | 2.24% |
| Delta PEEQ | 0.425% |

### 吊钩应变结果2

| | PEEQ |
|---|---|
| Step 2 | 1.34% |
| Step 4 | 1.35% |
| Delta PEEQ | 0.005% |

### 图片附件

![](../ocr/images/10e60b15b0f9fc6dd3c1073953cb5eb0c4561cbf4c1b862a5b46a5401a542fb8.jpg)

![](../ocr/images/eec6a91c08b98740faf025e8b3e7ba207c467dd3a5b49c2fc5b3959137474eed.jpg)

![](../ocr/images/ff81d172e13524cde1fdfc473352a743a9adf8a2e60451d6f7a63f3f2955b1df.jpg)

![](../ocr/images/78013dda7b43ce19b1dcd88ab3931e73c4b755e7abadfc106deed6f142085f30.jpg)

![](../ocr/images/83aba1d489596ee57882cebea09d3756b3fc7b2574d0607e46d7ccfa65991dbe.jpg)

![](../ocr/images/ea084fd2215c76375c7e2be78b2a86127f18426450e09855f28655bdcebe90eb.jpg)

---

## T6温度及温损验证 — RDE95 JIM 493 ATS POC Test

![](../ocr/images/12953689bb0f27665c28a60d44654f157c1038ca92655d48fb46c3743e41cde4.jpg)

![](../ocr/images/5f31e754369410d0e0734cab9ac222a501ca863748cb77fed9405c135694ff75.jpg)

---

## 其他附件图片

以下为OCR原始文件中未明确归类的图片引用，保留以便后续人工核对：

### 图纸/数模相关
- ![](../ocr/images/11527aa0d8788c1b64938c3ee2ffa1dc9959d5dfa79d8560f7e7c1576769d6b2.jpg)
- ![](../ocr/images/4f416fa6c8ce59cde5e732965b56494d060db7c6f55910731dc0a3ffa95560ae.jpg)
- ![](../ocr/images/4eae48faf946cfc29993d856e49933aacd27ee5b9ed8831923f8286280ca92a3.jpg)

### 仿真/分析结果
- ![](../ocr/images/66e3d293f7a99ccd4d26ad2ccc0fd789e04ceb5b03d92101b1819535bc25c38b.jpg)
- ![](../ocr/images/5538b4b3cf4e8485b621a4b96c6fcc6e2ab0740a30a3976c93e9cbfb543d963d.jpg)
- ![](../ocr/images/a65f0c2c9db0eae2b82cad0a95af348003a084ad3a2ab82e600cf4fd932c50a0.jpg)
- ![](../ocr/images/4775085bc16e01bfd6b80c98741919af6a7e54f23ee6fbd1182ff3a3dba64fe9.jpg)
- ![](../ocr/images/35b13e6fe117a13af313c47dca640e2a02c13d6fd5266bf7536172c259981b98.jpg)
- ![](../ocr/images/be06b7d38a39755585e2d4746bf7eb201e1d8699423945813ad0e770b9ee5300.jpg)
- ![](../ocr/images/5e8763888777adb9211c6920dd29c3227b12ba8699af52e3f513782133ee5d85.jpg)
- ![](../ocr/images/b92ee0b967698fc42a3decb199404588cec050853f7c74bcdf35a8f2d415986c.jpg)
- ![](../ocr/images/de13b0ef3392d50ed5565f60ba09451096d2d53e60cf7e5cec713b1fa1900036.jpg)
- ![](../ocr/images/ce81902f70068eb9d885bff982029a032cc56ee10dcd01cf7f6ed434b4a0a6b3.jpg)
- ![](../ocr/images/b2bf25340102125aee01638ea813c1c57b2bba2aba012031de7e088bd00c59d0.jpg)
- ![](../ocr/images/45106ccef87e4e981c294bb4e37c3c2abe24e9be89fa5dd433b5d39d50da7706.jpg)
- ![](../ocr/images/d0935c7a2b0a94714d85c862f7da44426fcfcafa8c345eabb14f011f9d1258c7.jpg)
- ![](../ocr/images/e305081223dd29a59f286d9dcb61ea86a6e51fec7f89b432b0a791c3257aed63.jpg)
- ![](../ocr/images/567245ee0bbcf4df64da75ae814277a3bae65375c368008c70d38911ad70577e.jpg)
- ![](../ocr/images/118fb27a1761f08c021b17f4b8dccef51b4e0b305caf08cd2b94db435886864d.jpg)
- ![](../ocr/images/1ec4ab40f8780921a644416ba3bd7ccddf1ba5ef21e7c867c2613277ba975563.jpg)
