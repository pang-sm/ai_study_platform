import "./LegalDocumentPage.css";

const UPDATED_AT = "2026年8月13日";

const DOCUMENTS = {
  terms: {
    title: "用户协议",
    intro: "欢迎使用智学AI——计算机学习智能体。请在使用服务前认真阅读本协议；注册、登录或继续使用服务，即表示你理解并同意本协议的约定。",
    sections: [
      ["agreement", "一、协议说明", "本协议适用于智学AI提供的学习服务。当前版本为 V1.0，更新日期为" + UPDATED_AT + "。平台可在合理范围内更新本协议，并在页面公布更新后的内容。"],
      ["service", "二、服务内容", "平台当前提供课程学习、11408 考试学习、编程学习、AI 对话与出题、学习计划和报告、资料与考试范围、Programming Workbench、会员权益、模拟支付及兑换码等功能。不同功能的可用范围、额度和有效期以页面实际展示为准。"],
      ["account", "三、注册与账户安全", "你应提供真实、准确且可维护的账户资料，并妥善保管账户和登录凭据。不得出租、出借、转让或以其他方式不当使用账户，也不得冒用他人身份访问服务。"],
      ["ai", "四、AI 学习功能", "AI 对话、题册、学习计划、学习报告及相关建议仅用于学习辅助。AI 输出可能存在错误、遗漏、不准确或不完整的情形，不构成对考试成绩、答案正确性或通过考试的保证。"],
      ["learning-data", "五、学习输入与记录", "为响应你的学习请求，平台会处理你提交的 AI 对话、练习内容、学习计划与报告相关信息，以及考试范围文本和知识点选择等学习数据。具体处理方式请参阅《隐私政策》。"],
      ["programming", "六、编程工作台", "你提交的源代码、输入、运行和提交记录及 AI Coach 对话，可能由平台运行环境处理。不得利用编程功能实施攻击、越权访问、绕过限制、恶意消耗计算资源或上传恶意代码。"],
      ["materials", "七、上传资料", "你应确保对上传资料拥有必要权利。平台仅可为你请求的学习功能，对资料进行存储、解析、知识结构整理和 AI 学习处理；这不表示平台取得你资料的无限商业使用权。"],
      ["membership", "八、会员、模拟支付与兑换码", "会员功能、额度、有效期及到期后的可用范围以实际页面为准。当前支付为模拟支付环境，不产生真实资金扣款，也不代表已提供真实收款、自动续费或退款机制。兑换码可能绑定服务、套餐、截止时间、权益期限或使用次数；过期、耗尽或撤销后不可继续使用，且不属于现金资产，不支持提现。"],
      ["conduct", "九、使用规范与内容权利", "不得上传违法、侵权或无权使用的内容，不得滥用 AI 或平台资源。平台的软件、界面和标识受相应权利保护；你对依法享有权利的上传内容和代码保留相应权利。AI 生成内容应结合实际情况自行判断和使用。"],
      ["service-change", "十、服务维护与责任边界", "平台可能因维护、升级、故障处理或安全需要调整、暂停部分服务。我们会在合理范围内尽力保障服务稳定；因网络、设备、第三方服务或其他非平台可控因素造成的影响，应依据实际情况处理。"],
      ["contact", "十一、运营与联系", "运营主体：\n【运营主体待正式补充】\n\n联系邮箱：\n【联系邮箱待正式补充】\n\n在正式公开商业运营前，平台将补充相应运营与联系信息。"],
    ],
  },
  privacy: {
    title: "隐私政策",
    intro: "本政策说明智学AI——计算机学习智能体在提供当前功能时处理哪些个人信息、用于什么目的，以及你目前可以使用的相关控制方式。",
    sections: [
      ["scope", "一、适用范围", "本政策适用于智学AI当前提供的服务，版本为 V1.0，更新日期为" + UPDATED_AT + "。平台遵循合法、正当、必要、诚信、公开透明、目的直接相关和最小范围的原则处理信息。"],
      ["account", "二、账户与资料信息", "为注册、登录、身份识别和个人资料展示，平台会处理用户名、昵称、头像，以及你选择填写的专业、年级、学期、学习方向和可选邮箱或手机号等信息。"],
      ["learning", "三、学习数据", "为保存学习进度、练习记录、复习状态、学习计划和报告，平台会处理相应的学习记录、练习回答和相关偏好信息。"],
      ["ai", "四、AI 功能与模型服务", "当你主动使用 AI 对话、出题、学习计划、学习报告或资料解析等功能时，相关输入、材料内容或必要上下文可能被发送给平台配置的 AI 模型服务提供方以完成该请求。当前内部审计识别到文本 AI 服务及 Qwen/DashScope 兼容的视觉或资料解析服务；具体调用取决于功能和运行配置。请勿在非必要情况下提交密码、API Key、银行卡信息、身份证号或其他无关敏感个人信息。"],
      ["materials", "五、资料、考试范围与知识内容", "为保存文件、解析内容、生成摘要或知识结构、构建考试范围和学习上下文，平台会处理你上传的资料及其元数据、提取文本、摘要、知识结构、考试范围文本和知识点选择。"],
      ["programming", "六、编程数据", "为执行代码、判题、展示历史记录和提供 AI Coach 功能，平台会处理你的项目、源文件、运行输入、运行结果、提交和相关历史记录。"],
      ["membership", "七、会员与兑换数据", "为识别服务权限、额度、有效期、订单状态和兑换审计，平台会处理会员套餐、权益额度、有效期、模拟订单和兑换使用记录等数据。当前支付为模拟支付环境，不产生真实资金扣款。"],
      ["session", "八、Cookie 与会话安全", "平台使用 ai_session Cookie 维持登录状态、完成身份验证并保护账户安全。该 Cookie 采用 HttpOnly、Secure 和 SameSite 等安全属性配置；请勿向他人透露你的登录凭据。"],
      ["storage", "九、保存与安全", "平台会在提供服务、安全防护、审计和必要运营所需的范围内保存相关信息，并采取与当前服务相适应的安全措施。具体统一保存期限将在正式公开商业运营前进一步明确。"],
      ["rights", "十、你可以进行的控制", "你目前可在产品中修改昵称、头像、专业、年级和学期，查看部分学习信息并退出登录；部分 AI 对话可单独删除。账户删除、完整数据导出或全量历史清除等请求渠道，将在正式运营主体和联系渠道公布后进一步明确。"],
      ["minors", "十一、未成年人提示", "平台当前未声明提供实名年龄验证、监护人同意或专门的未成年人保护机制。正式面向未成年人公开运营前，需要完成相应专项法律与产品审查。"],
      ["contact", "十二、运营与联系", "运营主体：\n【运营主体待正式补充】\n\n联系邮箱：\n【联系邮箱待正式补充】\n\n本政策更新时将通过本页面公布。"],
    ],
  },
};

function LegalDocumentPage({ documentType }) {
  const document = DOCUMENTS[documentType] || DOCUMENTS.terms;

  return (
    <main className="legal-page">
      <div className="legal-shell">
        <header className="legal-header">
          <a className="legal-brand" href="/" aria-label="返回登录或注册">智学AI</a>
          <a className="legal-back-link" href="/">返回登录 / 注册</a>
        </header>

        <article className="legal-document">
          <div className="legal-document-heading">
            <p className="legal-eyebrow">服务说明</p>
            <h1>{document.title}</h1>
            <p className="legal-meta">V1.0 · 更新日期：{UPDATED_AT}</p>
            <p className="legal-intro">{document.intro}</p>
          </div>

          <nav className="legal-toc" aria-label={`${document.title}目录`}>
            <h2>目录</h2>
            <ol>
              {document.sections.map(([id, heading]) => <li key={id}><a href={`#${id}`}>{heading}</a></li>)}
            </ol>
          </nav>

          <div className="legal-sections">
            {document.sections.map(([id, heading, content]) => (
              <section id={id} key={id} className="legal-section">
                <h2>{heading}</h2>
                {content.split("\n").map((paragraph, index) => paragraph ? <p key={`${id}-${index}`}>{paragraph}</p> : null)}
              </section>
            ))}
          </div>

          <footer className="legal-footer">
            <a className="legal-footer-link" href="/">返回登录 / 注册</a>
          </footer>
        </article>
      </div>
    </main>
  );
}

export default LegalDocumentPage;
